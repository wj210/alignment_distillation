"""Freeze two equal, globally deduplicated OCR2 Python question pools."""

import argparse
import json
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import HfApi, HfFileSystem

from distillation.common import digest, write_once

OCR2 = 'nvidia/OpenCodeReasoning-2'
REVISION = 'eadf535931451525f3e5621d0f960c240bc62fd9'
SUFFIX = '\n\nPlease provide the solution in Python.'


def group(difficulty):
    label = str(difficulty)
    if label in {'EASY', 'MEDIUM', 'introductory', 'interview'}:
        return 'easy_medium'
    if label in {'MEDIUM_HARD', 'HARD', 'VERY_HARD', 'competition'}:
        return 'hard_medium_hard'
    if label.isdigit():
        rating = int(label)
        if 800 <= rating <= 2100:
            return 'easy_medium'
        if 2200 <= rating <= 3500:
            return 'hard_medium_hard'
    return None


def read_shards(repo, revision, names, columns):
    def read(name):
        with HfFileSystem().open(f'datasets/{repo}@{revision}/{name}',
                                'rb', block_size=65536) as handle:
            return pq.read_table(handle, columns=columns).to_pylist()

    with ThreadPoolExecutor(max_workers=8) as pool:
        return [row for batch in pool.map(read, names) for row in batch]


def statement(row, dataset):
    if dataset in {'taco', 'apps'}:
        return row['question'].strip()
    prompt = row['description'].strip()
    if dataset == 'open-r1/codeforces':
        for field, title in [('input_format', 'Input'), ('output_format', 'Output')]:
            if row.get(field):
                prompt += f'\n\n{title}\n\n{row[field]}'
        if row.get('examples'):
            prompt += '\n\nExamples'
            for example in row['examples']:
                for field, title in [('input', 'Input'), ('output', 'Output')]:
                    if example.get(field):
                        prompt += f'\n\n{title}\n\n{example[field]}'
        for field, title in [('interaction_format', 'Interaction'), ('note', 'Note')]:
            if row.get(field):
                prompt += f'\n\n{title}\n\n{row[field]}'
    return prompt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('datasets/ocr2_16k'))
    parser.add_argument('--per-group', type=int, default=8000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    api = HfApi()
    info = api.dataset_info(OCR2, revision=REVISION)
    names = sorted(s.rfilename for s in info.siblings
                   if s.rfilename.startswith('train/python/') and s.rfilename.endswith('.parquet'))
    rows = read_shards(OCR2, REVISION, names,
                       ['question_id', 'dataset', 'split', 'index', 'source', 'difficulty'])
    unique = {}
    for row in rows:
        if group(row['difficulty']):
            unique.setdefault(row['question_id'], row)
    print(f'{len(unique)} eligible unique question IDs', flush=True)
    sources, revisions = {}, {}
    repositories = {'taco': 'BAAI/TACO', 'apps': 'codeparrot/apps',
                    'code_contests': 'deepmind/code_contests',
                    'open-r1/codeforces': 'open-r1/codeforces'}
    for dataset in sorted({r['dataset'] for r in unique.values()}):
        repo = repositories[dataset]
        source_info = api.dataset_info(repo, revision='refs/convert/parquet' if dataset == 'apps' else 'main')
        revisions[dataset] = {'repo': repo, 'revision': source_info.sha}
        columns = (['question'] if dataset in {'taco', 'apps'} else
                   ['description', 'input_format', 'output_format', 'examples', 'interaction_format', 'note']
                   if dataset == 'open-r1/codeforces' else ['description'])
        for split in sorted({r['split'] for r in unique.values() if r['dataset'] == dataset}):
            prefix = f'ALL/{split}-' if dataset == 'taco' else f'all/{split}/' if dataset == 'apps' else f'data/{split}-'
            names = sorted(s.rfilename for s in source_info.siblings
                           if s.rfilename.startswith(prefix) and s.rfilename.endswith('.parquet'))
            assert names, (dataset, split)
            sources[dataset, split] = read_shards(repo, source_info.sha, names, columns)
        print(f'Loaded {dataset} source statements', flush=True)
    pools = {'easy_medium': [], 'hard_medium_hard': []}
    seen, duplicates = {}, []
    for question_id, row in sorted(unique.items()):
        source = sources[row['dataset'], row['split']][int(row['index'])]
        text = statement(source, row['dataset'])
        assert text
        canonical_id = digest(' '.join(text.split()))
        if canonical_id in seen:
            duplicates.append({'question_id': question_id, 'retained_id': seen[canonical_id]})
            continue
        seen[canonical_id] = question_id
        label = group(row['difficulty'])
        pools[label].append({**row, 'group': label, 'domain': 'code',
                             'id': digest(text + SUFFIX), 'canonical_prompt_id': canonical_id,
                             'prompt': text + SUFFIX})
    rng = random.Random(args.seed)
    selected = []
    for label, pool in pools.items():
        if len(pool) < args.per_group:
            raise ValueError(f'{label}: only {len(pool)} unique statements for {args.per_group} requested')
        selected.extend(rng.sample(pool, args.per_group))
    rng.shuffle(selected)
    assert len({r['id'] for r in selected}) == len({r['question_id'] for r in selected}) == len(selected)
    assert len({r['canonical_prompt_id'] for r in selected}) == len(selected)
    args.output.mkdir(parents=True, exist_ok=True)
    write_once(args.output / 'prompts.jsonl', selected)
    for label in pools:
        write_once(args.output / f'{label}.jsonl', [r for r in selected if r['group'] == label])
    manifest = {'dataset': OCR2, 'revision': REVISION, 'source_revisions': revisions,
                'seed': args.seed, 'per_group': args.per_group,
                'eligible_ids': len(unique), 'unique_statement_pools': {k: len(v) for k, v in pools.items()},
                'duplicate_statements_dropped': len(duplicates),
                'deduplication': 'global collapsed whitespace; stable question-ID order retains first duplicate',
                'selected_counts': dict(Counter(r['group'] for r in selected)),
                'source_counts': dict(Counter(r['dataset'] for r in selected)),
                'safety_filter': 'not yet applied', 'generation': 'not started',
                'prompt_suffix': SUFFIX, 'prompts_sha256': digest((args.output / 'prompts.jsonl').read_bytes())}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (args.output / 'duplicates.json').write_text(json.dumps(duplicates, indent=2) + '\n')
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == '__main__':
    main()
