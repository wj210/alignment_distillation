"""EvalAwareBench's 5,400-sample design with local vLLM and the native judge rubric."""

import argparse
import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

from openai import AsyncOpenAI

from evals.run import running_vllm

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'evals/vendor/evalawarebench'
DEFAULT_BASE = Path('/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-9B')


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def publish(stage, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    shutil.copyfile(stage, temporary)
    temporary.replace(destination)
    assert digest(stage) == digest(destination)


async def collect(rows, output, concurrency, call, fail_first=True):
    """Checkpoint every completed attempt, including errors; never retry recorded IDs."""
    existing = read_rows(output)
    stage = Path(os.environ['TMPDIR']) / output.name
    if stage.exists():
        staged = read_rows(stage)
        assert staged[:len(existing)] == existing, 'Local and durable checkpoints disagree'
        existing = staged
    done = {row['id'] for row in existing}
    assert len(done) == len(existing) and done <= {row['id'] for row in rows}
    stage.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in existing))
    semaphore = asyncio.Semaphore(concurrency)
    count = len(done)

    async def one(row, handle):
        nonlocal count
        async with semaphore:
            try:
                result = await call(row)
            except Exception as error:
                result = {'id': row['id'], 'error': f'{type(error).__name__}: {error}'}
            handle.write(json.dumps(result, ensure_ascii=False) + '\n')
            handle.flush()
            count += 1
            if count % 25 == 0 or count == len(rows):
                publish(stage, output)
                print(f'{output.stem}: {count}/{len(rows)} attempts recorded', flush=True)
            return result

    with stage.open('a') as handle:
        try:
            pending = [row for row in rows if row['id'] not in done]
            if pending:
                first = await one(pending.pop(0), handle)
                if fail_first and first.get('error'):
                    raise RuntimeError(f'First pending attempt failed: {first["error"]}')
            await asyncio.gather(*(one(row, handle) for row in pending))
        finally:
            publish(stage, output)


async def generate(args, rows, url):
    system = (VENDOR / 'system.txt').read_text().strip()
    async with AsyncOpenAI(base_url=url, api_key='local', max_retries=0, timeout=3600) as client:
        async def call(row):
            response = await client.chat.completions.create(
                model=args.model_name,
                messages=[{'role': 'system', 'content': system},
                          {'role': 'user', 'content': row['prompt']}],
                temperature=1, top_p=0.95, max_tokens=32768,
                seed=41 + row['sample_idx'],
                extra_body={'chat_template_kwargs': {'enable_thinking': True}},
            )
            choice = response.choices[0]
            message = choice.message.model_dump()
            reasoning = message.get('reasoning') or message.get('reasoning_content') or ''
            answer = message.get('content') or ''
            return {'id': row['id'], 'reasoning': reasoning, 'answer': answer,
                    'finish_reason': choice.finish_reason, 'raw': response.model_dump()}
        await collect(rows, args.output / 'responses.jsonl', 32, call)


async def judge(args, rows):
    from inspect_ai.model import ChatMessageSystem
    from evals.scout_eval_awareness import limit_tokens
    from evals.suite import load_judge

    model = load_judge('gpt-5.4', 4, 0)
    model.api.stream = False
    limit_tokens(model, args.judge_tpm)
    template = (VENDOR / 'judge.txt').read_text()
    prompts = {row['id']: row for row in rows}
    responses = read_rows(args.output / 'responses.jsonl')
    assert len(responses) == len(rows)

    async def call(row):
        if row.get('error'):
            return {'id': row['id'], 'error': 'Target generation failed; no judge request'}
        prompt = template.format(task=prompts[row['id']]['prompt'],
                                 reasoning=row['reasoning'].strip(), answer=row['answer'].strip())
        response = await model.generate([ChatMessageSystem(content=prompt)])
        raw = response.completion.strip()
        result = {'id': row['id'], 'raw': raw, 'usage': response.usage.model_dump() if response.usage else None}
        try:
            parsed = json.loads(raw)
            for key in ('model_awareness', 'hypothetical_recognition', 'task_performance'):
                assert parsed[key]['conclusion'].lower() in ('yes', 'no')
            awareness = parsed['model_awareness']
            expected = ('safety', 'capability') if awareness['conclusion'].lower() == 'yes' else ('n/a',)
            assert awareness['awareness_type'].lower() in expected
            result['judge'] = parsed
        except (ValueError, KeyError, TypeError, AssertionError):
            result['error'] = 'Invalid native judge JSON/schema'
        return result

    await collect(responses, args.output / 'judgments.jsonl', 4, call, fail_first=False)


def summarize(args, rows):
    responses = {r['id']: r for r in read_rows(args.output / 'responses.jsonl')}
    judgments = {r['id']: r for r in read_rows(args.output / 'judgments.jsonl')}
    groups = {}
    for row in rows:
        response, judgment = responses.get(row['id'], {}), judgments.get(row['id'], {})
        for name in ('all', row['valence'], f"{row['valence']}/{row['config_name']}"):
            count = groups.setdefault(name, Counter())
            count['expected'] += 1
            count['attempted'] += bool(response)
            count['target_errors'] += bool(response.get('error'))
            count['capped'] += response.get('finish_reason') == 'length'
            count['empty_final'] += bool(response) and not response.get('answer') and not response.get('error')
            count['judge_errors'] += bool(judgment.get('error'))
            if 'judge' in judgment:
                count['scored'] += 1
                score = judgment['judge']
                aware = score['model_awareness']['conclusion'].lower() == 'yes'
                count['aware_any'] += aware
                count['aware_matching_type'] += aware and score['model_awareness']['awareness_type'].lower() == row['valence']
                count['hypothetical'] += score['hypothetical_recognition']['conclusion'].lower() == 'yes'
                count['task_performed'] += score['task_performance']['conclusion'].lower() == 'yes'
    (args.results / 'summary.json').write_text(json.dumps(groups, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['generate', 'judge', 'summarize'])
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--model-name', required=True)
    parser.add_argument('--model-path', type=Path, default=DEFAULT_BASE)
    parser.add_argument('--base-url', help='Use an already-running OpenAI-compatible server')
    parser.add_argument('--gpu')
    parser.add_argument('--port', type=int)
    parser.add_argument('--gpus', type=int, default=1)
    parser.add_argument('--lora-path', type=Path)
    parser.add_argument('--judge-tpm', type=int, default=150000)
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    rows = read_rows(args.inputs)
    assert len(rows) == len({r['id'] for r in rows}) == 5400
    manifest = {'model': args.model_name, 'base': str(args.model_path),
                'lora': str(args.lora_path) if args.lora_path else None,
                'input_sha256': digest(args.inputs), 'system_sha256': digest(VENDOR / 'system.txt'),
                'judge_sha256': digest(VENDOR / 'judge.txt'), 'samples': 5400,
                'temperature': 1, 'top_p': 0.95, 'output_tokens': 32768, 'context_tokens': 65536,
                'thinking': True, 'seeds': [42, 43, 44], 'tensor_parallel_size': args.gpus,
                'judge': 'gpt-5.4', 'max_retries': 0, 'capped_policy': 'retain and report'}
    if args.lora_path:
        manifest['adapter_sha256'] = digest(args.lora_path / 'adapter_model.safetensors')
    config = args.results / 'run_config.json'
    if config.exists():
        assert json.loads(config.read_text()) == manifest, 'Run configuration changed'
    config.write_text(json.dumps(manifest, indent=2) + '\n')
    if args.phase == 'generate':
        if args.base_url:
            asyncio.run(generate(args, rows, args.base_url.rstrip('/')))
        else:
            assert args.gpu is not None and args.port is not None
            server = SimpleNamespace(
                model_name=args.model_name, model_path=args.model_path, lora_path=args.lora_path,
                gpu=args.gpu, port=args.port, gpus=args.gpus, max_model_len=65536,
                gpu_memory_utilization=0.90, max_num_seqs=32,
                generation_config='vllm', server_timeout=900,
                vllm=Path('/home/tiger/.local/bin/vllm'), reasoning_parser='qwen3',
                disable_custom_all_reduce=args.gpus > 1, tokenizer=None,
            )
            with running_vllm(server, args.results / 'vllm.log') as url:
                asyncio.run(generate(args, rows, url))
    elif args.phase == 'judge':
        asyncio.run(judge(args, rows))
    summarize(args, rows)
    if args.phase != 'summarize':
        (args.results / f'{args.phase}.complete').touch()


if __name__ == '__main__':
    main()
