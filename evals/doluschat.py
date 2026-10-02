"""Evaluate both DS4F teachers on a cached DolusChat sample, then judge with Terra.

Run with the project evaluation environment; judge subprocesses use the separate
LiteLLM environment to avoid dependency conflicts. Existing attempts are never retried.
"""
import hashlib
import json
import random
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq
from dotenv import dotenv_values
from openai import OpenAI

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from distillation.generate import generate_one

ROOT = PROJECT / 'results/ds4f_doluschat_1000_terra_20260928'
CACHE = PROJECT / 'datasets/doluschat/eval_1000_seed42.json'
JUDGE_PYTHON = '/tmp/alignment-mask-judge/bin/python'
TEACHERS = {'april': ('deepseek/deepseek-v4-flash', 'gmicloud/fp8'),
            'july': ('deepseek/deepseek-v4-flash-0731', 'streamlake/fp8')}


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def prepare():
    ROOT.mkdir(exist_ok=True)
    if not CACHE.exists():
        rows = pq.read_table(PROJECT / 'datasets/doluschat/eval.parquet').to_pylist()
        rows = random.Random(42).sample(sorted(rows, key=lambda row: row['sample_id']), 1000)
        staged = Path('/tmp/doluschat_eval_1000_seed42.json')
        save(staged, rows)
        shutil.copyfile(staged, CACHE)
        assert staged.read_bytes() == CACHE.read_bytes()
    rows = json.loads(CACHE.read_text())
    assert len(rows) == len({r['sample_id'] for r in rows}) == 1000
    source = pq.read_table(PROJECT / 'datasets/doluschat/eval.parquet').to_pylist()
    by_id = {r['sample_id']: r for r in source}
    assert all(r == by_id[r['sample_id']] for r in rows)
    config = {'teachers': TEACHERS, 'sample_file': str(CACHE.relative_to(PROJECT)),
        'sample_sha256': hashlib.sha256(CACHE.read_bytes()).hexdigest(),
        'selection': 'random.Random(42).sample(eval sorted by sample_id, 1000)',
        'reasoning_effort': 'high', 'concurrency_per_teacher': 32, 'temperature': 1,
        'top_p': 0.95, 'max_tokens': 32768, 'retries': 0, 'fallbacks': False,
        'judge': 'gpt-5.6-terra', 'judge_route': 'LiteLLM ChatGPT subscription',
        'judge_effort': 'low', 'judge_concurrency': 8, 'judge_timeout_seconds': 240,
        'judge_output_limit': 'subscription default',
        'judge_protocol': 'Unchanged five-example pilot rubric: truthfulness and refusal independently; no references or target reasoning'}
    judge_prompt = (PROJECT / 'results/ds4f_doluschat_5_20260928/judge_system.txt').read_text()
    config['judge_prompt_sha256'] = hashlib.sha256(judge_prompt.encode()).hexdigest()
    if (ROOT / 'config.json').exists():
        assert json.loads((ROOT / 'config.json').read_text()) == json.loads(json.dumps(config))
    save(ROOT / 'config.json', config)
    (ROOT / 'judge_system.txt').write_text(judge_prompt)
    return rows


def generate(client, teacher, row, root=None):
    folder = (ROOT if root is None else root) / teacher / row['sample_id']
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'generation.json'
    if path.exists():
        return row, folder, json.loads(path.read_text())
    if (folder / 'generation_started').exists():
        return row, folder, {'complete': False, 'error': 'Interrupted previous attempt; no retry'}
    (folder / 'generation_started').touch()
    model, provider = TEACHERS[teacher]
    args = SimpleNamespace(model=model, system_prompt=row['messages'][0]['content'], seed=None,
        max_tokens=32768, token_limit_field='max_tokens', chat_template_kwargs={}, max_retries=0,
        sampling_params={'temperature': 1, 'top_p': 0.95, 'extra_body': {
            'reasoning': {'effort': 'high', 'exclude': False},
            'provider': {'only': [provider], 'allow_fallbacks': False, 'require_parameters': True}}})
    try:
        result = generate_one(client, {'id': row['sample_id'], 'prompt': row['messages'][1]['content']}, args)
    except Exception as error:
        result = {'complete': False, 'error': str(error), 'response': '', 'reasoning': ''}
    result.update(teacher=teacher, sample_id=row['sample_id'], source_row=row['source_row'])
    save(path, result)
    return row, folder, result


def judge(row, folder, result):
    folder = folder / 'judge'
    if folder.exists():
        return  # A started judge attempt is never repeated, including failed attempts.
    folder.mkdir()
    prompt = ('<|start_header_id|>system<|end_header_id|>\n\n' + row['messages'][0]['content']
        + '<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n' + row['messages'][1]['content']
        + '<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n')
    (folder / 'input.txt').write_text(f"<input>Prompt:\n{prompt}\nResponse:\n{result['response']}</input>")
    try:
        with (folder / 'process.log').open('w') as log:
            process = subprocess.run([JUDGE_PYTHON, str(PROJECT / 'evals/doluschat_judge.py'),
                str(folder), str(ROOT / 'judge_system.txt')], stdout=log, stderr=subprocess.STDOUT, timeout=270)
        if process.returncode:
            save(folder / 'error.json', {'error': f'Judge exited {process.returncode}; see process.log'})
    except Exception as error:
        save(folder / 'error.json', {'error': str(error)})


def run_teacher(client, pool, teacher, rows):
    with ThreadPoolExecutor(max_workers=32) as generation_pool:
        jobs = [generation_pool.submit(generate, client, teacher, row) for row in rows]
        judging = []
        for count, future in enumerate(as_completed(jobs), 1):
            row, folder, result = future.result()
            if result['complete']:
                judging.append(pool.submit(judge, row, folder, result))
            save(ROOT / f'{teacher}_status.json', {'generation_finished': count, 'total': len(rows)})
            if count % 50 == 0:
                print(teacher, 'generation', count, flush=True)
        for future in as_completed(judging):
            future.result()
    print(teacher, 'finished', flush=True)


def main():
    rows = prepare()
    started = time.time()
    save(ROOT / 'status.json', {'status': 'running', 'started_unix': started})
    with OpenAI(base_url='https://openrouter.ai/api/v1', max_retries=0, timeout=600,
                api_key=dotenv_values(PROJECT / '.env')['OPENROUTER_API_KEY']) as client:
        with ThreadPoolExecutor(max_workers=8) as judge_pool, ThreadPoolExecutor(max_workers=2) as teachers:
            jobs = [teachers.submit(run_teacher, client, judge_pool, teacher, rows) for teacher in TEACHERS]
            for future in as_completed(jobs):
                future.result()
    save(ROOT / 'status.json', {'status': 'finished', 'wall_seconds': time.time()-started})


if __name__ == '__main__':
    main()
