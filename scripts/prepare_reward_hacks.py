"""Cache the pinned School of Reward Hacks release without changing its prompts."""
import csv
import hashlib
import io
import json
import shutil
from collections import Counter
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parents[1]
REVISION = 'd7e04a550119cb5410494cf90e2313284a5f2148'
COMMIT = '42dfd6481f62f6dff1f976e4a3af3083d731231e'


def main():
    stage = Path('/tmp/reward_hacks_data')
    stage.mkdir(exist_ok=True)
    sources = {
        'source.csv': f'https://huggingface.co/datasets/longtermrisk/school-of-reward-hacks/resolve/{REVISION}/school-of-reward-hacks.csv',
        'paper.pdf': f'https://raw.githubusercontent.com/msimontaylor/school-of-reward-hacks/{COMMIT}/school-of-reward-hacks.pdf',
    }
    for name, url in sources.items():
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        (stage / name).write_bytes(response.content)
    rows = list(csv.DictReader(io.StringIO((stage / 'source.csv').read_text())))
    for index, row in enumerate(rows):
        row.update(source_row=index, sample_id=hashlib.sha256(row['user'].encode()).hexdigest(),
                   messages=[{'role': 'system', 'content': ''},
                             {'role': 'user', 'content': row['user']}])
    assert len(rows) == len({row['sample_id'] for row in rows}) == 1073
    (stage / 'samples.json').write_text(json.dumps(rows, indent=2) + '\n')
    manifest = {
        'dataset': 'longtermrisk/school-of-reward-hacks', 'revision': REVISION,
        'source_repository': 'https://github.com/msimontaylor/school-of-reward-hacks',
        'repository_commit': COMMIT, 'repository_contents': 'paper PDF only; no evaluation harness',
        'count': len(rows), 'tasks': dict(Counter(row['task'] for row in rows)),
        'files': {name: hashlib.sha256((stage / name).read_bytes()).hexdigest()
                  for name in ('source.csv', 'paper.pdf', 'samples.json')},
        'model_input': 'Original user field only; no added system instruction. Empty system field in cache is omitted by generator. No references or task metadata sent to teachers.',
    }
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    destination = PROJECT / 'datasets/school_of_reward_hacks'
    destination.mkdir(parents=True, exist_ok=True)
    for name in (*manifest['files'], 'manifest.json'):
        target = destination / name
        if target.exists():
            assert target.read_bytes() == (stage / name).read_bytes(), f'Frozen file differs: {target}'
        else:
            shutil.copyfile(stage / name, target)
        assert target.read_bytes() == (stage / name).read_bytes()
    print(f'Verified {len(rows)} cached prompts in {destination}')


if __name__ == '__main__':
    main()
