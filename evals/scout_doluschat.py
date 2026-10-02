"""Run the unchanged awareness scanner on saved complete teacher answers."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
from pathlib import Path

from inspect_ai.model import ChatMessageSystem, ChatMessageUser, ChatMessageAssistant, ContentReasoning, ContentText, Model, GenerateConfig
from inspect_scout import Transcript, scan, transcripts_db, transcripts_from
from pydantic import TypeAdapter

from evals.scanners.eval_awareness import eval_awareness
from evals.scout_terra import TerraSubscription

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/ds4f_doluschat_1000_terra_20260928'
DEST = ROOT / 'results/ds4f_doluschat_1000_eval_awareness_20260928'


async def insert(path, transcripts):
    async with transcripts_db(str(path)) as db:
        await db.insert(transcripts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--dest', type=Path, default=DEST)
    parser.add_argument('--samples', type=Path, default=ROOT / 'datasets/doluschat/eval_1000_seed42.json')
    parser.add_argument('--task-set', default='doluschat')
    parser.add_argument('--teachers', nargs='+', choices=['april', 'july'], default=['april', 'july'])
    args = parser.parse_args()
    dest = args.dest / 'preflight' if args.preflight else args.dest
    dest.mkdir(parents=True, exist_ok=True)
    source_hashes, transcripts = {}, []
    rows = json.loads(args.samples.read_text())
    excluded = []
    for row in rows:
        for teacher in args.teachers:
            path = (args.source / teacher / row['sample_id'] / 'generation.json').resolve()
            result = json.loads(path.read_text())
            if not result['complete']:
                excluded.append(f"{teacher}:{row['sample_id']}")
                continue
            source_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
            content = [ContentReasoning(reasoning=result['reasoning'])] if result['reasoning'] else []
            content.append(ContentText(text=result['response']))
            transcripts.append(Transcript(transcript_id=f"{teacher}:{row['sample_id']}",
                task_id=row['sample_id'], task_set=args.task_set, model=teacher,
                source_type='teacher_json', source_uri=str(path),
                metadata={'teacher': teacher, 'source_row': row['source_row']},
                messages=[ChatMessageSystem(content=row['messages'][0]['content']),
                    ChatMessageUser(content=row['messages'][1]['content']),
                    ChatMessageAssistant(content=content)]))
    assert len(transcripts) + len(excluded) == len(args.teachers) * len(rows)
    if args.preflight:
        transcripts = transcripts[:2]
    scanner_path = ROOT / 'evals/scanners/eval_awareness.py'
    provenance = json.loads(scanner_path.with_suffix('.provenance.json').read_text())
    assert hashlib.sha256(scanner_path.read_bytes()).hexdigest() == provenance['sha256']
    manifest = {'sources': source_hashes, 'scanner': provenance, 'count': len(transcripts),
        'judge': 'gpt-5.6-terra', 'route': 'LiteLLM ChatGPT subscription', 'effort': 'low',
        'concurrency': 32, 'retries': 0, 'include': 'full system/user context, exposed reasoning and final answer',
        'excluded': excluded,
        'versions': {p: importlib.metadata.version(p) for p in ['inspect-scout', 'inspect-ai']}}
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    database = Path('/tmp') / (dest.parent.name + '_preflight' if args.preflight else dest.name + '_transcripts')
    asyncio.run(insert(database, transcripts))
    config = GenerateConfig(max_connections=32, max_retries=0, reasoning_effort='low')
    judge = Model(TerraSubscription(dest / 'calls'), config=config)
    status = scan(scanners=[eval_awareness()], transcripts=transcripts_from(str(database)),
        model=judge, scans=str(dest / 'scans'), max_processes=1, max_transcripts=32,
        results_buffer=1, display='plain', fail_on_error=False)
    (dest / 'scan_status.json').write_bytes(TypeAdapter(type(status)).dump_json(status, indent=2))


if __name__ == '__main__':
    main()
