"""Run the unchanged eval-awareness scanner directly on Inspect evaluation logs."""

import argparse
import asyncio
import importlib.metadata
import json
from collections import Counter
from pathlib import Path

from inspect_scout import scan, transcripts_from
from pydantic import TypeAdapter

from evals.scanners.eval_awareness import eval_awareness
from evals.scout_eval_awareness import limit_tokens, sha256
from evals.suite import load_judge


async def transcript_index(transcripts):
    async with transcripts.reader() as reader:
        return [row async for row in reader.index()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs', type=Path)
    parser.add_argument('--results', required=True, type=Path)
    parser.add_argument('--expected-transcripts', type=int, default=600)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--tpm', type=int, default=450000)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    assert args.tpm > 0 and args.concurrency > 0
    paths = sorted(args.logs.rglob('*.eval'))
    assert paths, 'No Inspect evaluation logs found'
    hashes = {str(path.resolve()): sha256(path) for path in paths}
    transcripts = transcripts_from([str(path.resolve()) for path in paths])
    index = asyncio.run(transcript_index(transcripts))
    assert len(index) == args.expected_transcripts, f'Expected {args.expected_transcripts} transcripts; found {len(index)}'
    assert len({row.transcript_id for row in index}) == len(index), 'Duplicate transcript IDs'
    scanner = Path(__file__).parent / 'scanners' / 'eval_awareness.py'
    provenance = json.loads(scanner.with_suffix('.provenance.json').read_text())
    assert sha256(scanner) == provenance['sha256'], 'Official scanner was modified'
    manifest = {'sources': hashes, 'scanner': provenance,
                'inspect_scout': importlib.metadata.version('inspect_scout'),
                'transcripts': len(index), 'models': dict(Counter(row.model for row in index)),
                'judge': 'gpt-5.4', 'concurrency': args.concurrency, 'max_retries': 0,
                'token_limiter': {'tpm': args.tpm, 'window_seconds': 60, 'encoding': 'o200k_base',
                                  'input_safety_factor': 1.25, 'output_reservation': 512}}
    assert all(sha256(path) == hashes[str(path.resolve())] for path in paths), 'Logs changed during indexing'
    args.results.mkdir(parents=True, exist_ok=True)
    manifest_path = args.results / 'scan_inputs.json'
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest, 'Inputs or settings changed'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Scanning {len(index)} transcripts: {manifest["models"]}', flush=True)
    judge = load_judge('gpt-5.4', args.concurrency, 0)
    judge.api.stream = False
    limit_tokens(judge, args.tpm)
    status = scan(scanners=[eval_awareness()], transcripts=transcripts, model=judge,
                  scans=str(args.results / 'scans'), max_processes=1,
                  max_transcripts=args.concurrency, results_buffer=1, display='rich',
                  dry_run=args.dry_run, metadata={'input_manifest': str(manifest_path.resolve())})
    filename = 'dry_run_status.json' if args.dry_run else 'scan_status.json'
    (args.results / filename).write_bytes(TypeAdapter(type(status)).dump_json(status, indent=2) + b'\n')


if __name__ == '__main__':
    main()
