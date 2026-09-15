"""Scan frozen matched teacher transcripts with Scout's unchanged official rubric."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import time
from collections import deque
from functools import wraps

import tiktoken
from pathlib import Path

from pydantic import TypeAdapter

from inspect_ai.model import ChatMessageAssistant, ChatMessageUser, ContentReasoning, ContentText
from inspect_scout import Transcript, scan, scan_resume, transcripts_db, transcripts_from

from evals.scanners.eval_awareness import eval_awareness
from evals.suite import load_judge


def limit_tokens(judge, tpm, window=60):
    """Reserve estimated request tokens in one shared rolling window."""
    encoder = tiktoken.get_encoding('o200k_base')
    pending, lock = deque(), asyncio.Lock()
    original = judge.generate

    def serialize(value):
        if hasattr(value, 'model_dump'):
            return value.model_dump(mode='json', exclude_none=True)
        return {'name': value.name, 'description': value.description,
                'parameters': value.parameters.model_dump(mode='json')}

    @wraps(original)
    async def generate(input, tools=(), **kwargs):
        payload = json.dumps({'messages': input, 'tools': tools}, default=serialize, ensure_ascii=False)
        tokens = math.ceil(len(encoder.encode(payload, disallowed_special=())) * 1.25) + 512
        if tokens > tpm:
            raise ValueError(f'Request reservation {tokens} exceeds TPM budget {tpm}')
        while True:
            async with lock:
                now = time.monotonic()
                while pending and pending[0][0] <= now - window:
                    pending.popleft()
                if sum(n for _, n in pending) + tokens <= tpm:
                    pending.append((now, tokens))
                    break
                delay = pending[0][0] + window - now
            await asyncio.sleep(delay)
        return await original(input, tools=tools, **kwargs)

    judge.generate = generate


def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read_pairs(ids_path, data, prompts_path, expected_pairs):
    with ids_path.open() as handle:
        rows = json.load(handle) if ids_path.suffix == '.json' else [json.loads(line) for line in handle if line.strip()]
    ids = [row if isinstance(row, str) else row['id'] for row in rows]
    assert len(ids) == len(set(ids)) == expected_pairs, 'Expected distinct frozen prompt IDs'
    with prompts_path.open() as handle:
        prompts = {row['id']: row for row in map(json.loads, handle) if row['id'] in ids}
    assert set(prompts) == set(ids)
    assert all(row['source'] == 'openthoughts' for row in prompts.values())
    answers = {}
    for teacher in ['april', 'july']:
        selected = {}
        with (data / teacher / 'answers.jsonl').open() as handle:
            for row in map(json.loads, handle):
                if row['id'] in prompts:
                    assert row['id'] not in selected, 'Duplicate teacher response ID'
                    assert row.get('complete') and row.get('response', '').strip()
                    assert row['prompt'] == prompts[row['id']]['prompt']
                    selected[row['id']] = row
        assert set(selected) == set(ids), f'Missing matched responses: {teacher}'
        answers[teacher] = selected
    for identifier in ids:
        for teacher, selected in answers.items():
            row = selected[identifier]
            content = []
            if row.get('reasoning'):
                content.append(ContentReasoning(reasoning=row['reasoning']))
            content.append(ContentText(text=row['response']))
            yield Transcript(
                transcript_id=f'{teacher}:{identifier}', task_id=identifier,
                task_set='openthoughts', model=teacher, source_type='teacher_jsonl',
                source_uri=str((data / teacher / 'answers.jsonl').resolve()),
                metadata={'teacher': teacher, 'domain': prompts[identifier]['domain']},
                messages=[ChatMessageUser(content=row['prompt']), ChatMessageAssistant(content=content)],
            )


async def import_transcripts(path, transcripts):
    async with transcripts_db(str(path)) as db:
        await db.insert(transcripts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ids', type=Path, default=Path('results/deepseek_openthoughts_eval_awareness/filter/prompts.jsonl'))
    parser.add_argument('--data', type=Path, default=Path('data/wildchat_openthoughts/labels'))
    parser.add_argument('--prompts', type=Path, default=Path('data/wildchat_openthoughts/prompts.jsonl'))
    parser.add_argument('--results', type=Path, default=Path('results/deepseek_openthoughts_eval_awareness'))
    parser.add_argument('--transcripts', type=Path, default=Path('/tmp/deepseek_openthoughts_eval_awareness_transcripts'))
    parser.add_argument('--expected-pairs', type=int, default=500)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--max-retries', type=int, default=2)
    parser.add_argument('--tpm', type=int, default=450000, help='Rolling 60-second token reservation budget')
    parser.add_argument('--resume', type=str, help='Existing Scout scan directory to resume')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    assert args.tpm > 0, 'TPM budget must be positive'
    assert not args.resume, 'TPM-limited execution requires a fresh scan; Scout resume rebuilds the judge'
    assert not (args.resume and args.dry_run), 'Resume runs API requests; omit --dry-run'
    sources = [args.ids, args.prompts, *(args.data / t / 'answers.jsonl' for t in ['april', 'july'])]
    scanner = Path(__file__).parent / 'scanners' / 'eval_awareness.py'
    provenance = json.loads(scanner.with_suffix('.provenance.json').read_text())
    assert sha256(scanner) == provenance['sha256'], 'Official scanner was modified'
    manifest = {'sources': {str(p.resolve()): sha256(p) for p in sources},
                'scanner': provenance, 'inspect_scout': importlib.metadata.version('inspect_scout'),
                'expected_pairs': args.expected_pairs, 'judge': 'gpt-5.4',
                'concurrency': args.concurrency, 'max_retries': args.max_retries,
                'token_limiter': {'tpm': args.tpm, 'window_seconds': 60,
                                  'encoding': 'o200k_base', 'input_safety_factor': 1.25, 'output_reservation': 512}}
    args.results.mkdir(parents=True, exist_ok=True)
    manifest_path = args.results / 'scan_inputs.json'
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest, 'Inputs or scan configuration changed'
    transcripts = list(read_pairs(args.ids, args.data, args.prompts, args.expected_pairs))
    assert all(sha256(p) == manifest['sources'][str(p.resolve())] for p in sources), 'Inputs changed while reading'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    judge = load_judge('gpt-5.4', args.concurrency, args.max_retries)
    judge.api.stream = False  # Gateway tool-call chunks are incompatible with SDK streaming.
    limit_tokens(judge, args.tpm)
    if args.resume:
        status = scan_resume(args.resume, display='rich')
    else:
        db_manifest = args.transcripts.with_suffix('.inputs.json')
        if args.transcripts.exists():
            assert db_manifest.exists() and json.loads(db_manifest.read_text()) == manifest, 'Transcript database belongs to different inputs'
        db_manifest.parent.mkdir(parents=True, exist_ok=True)
        db_manifest.write_text(json.dumps(manifest, indent=2) + '\n')
        asyncio.run(import_transcripts(args.transcripts, transcripts))
        status = scan(scanners=[eval_awareness()], transcripts=transcripts_from(str(args.transcripts)),
                      model=judge, scans=str(args.results / 'scans'), max_processes=1,
                      max_transcripts=args.concurrency, results_buffer=1, display='rich',
                      dry_run=args.dry_run, metadata={'input_manifest': str(manifest_path.resolve())})
    (args.results / ('dry_run_status.json' if args.dry_run else 'scan_status.json')).write_bytes(TypeAdapter(type(status)).dump_json(status, indent=2) + b'\n')


if __name__ == '__main__':
    main()
