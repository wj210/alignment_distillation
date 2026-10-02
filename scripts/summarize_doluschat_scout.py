"""Read native Scout results and join awareness labels with honesty labels."""
import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / 'results/ds4f_doluschat_1000_eval_awareness_20260928'
SOURCE = ROOT / 'results/ds4f_doluschat_1000_terra_20260928'


def main():
    paths = list((SCAN / 'scans').glob('*/eval_awareness.parquet'))
    assert len(paths) == 1
    columns = ['transcript_id', 'value', 'explanation', 'metadata', 'scan_error']
    records = pq.read_table(paths[0], columns=columns).to_pylist()
    labels = []
    for r in records:
        teacher, sample_id = r['transcript_id'].split(':')
        metadata = json.loads(r['metadata'] or '{}')
        score = float(r['value']) if r['value'] is not None else None
        value = {1.0: 'YES', 0.5: 'UNSURE', 0.0: 'NO'}.get(score)
        generation = json.loads((SOURCE / teacher / sample_id / 'generation.json').read_text())
        honesty = json.loads((SOURCE / teacher / sample_id / 'judge/judgment.json').read_text())
        labels.append({'teacher': teacher, 'sample_id': sample_id, 'source_row': generation['source_row'],
            'awareness': value, 'explanation': r['explanation'], 'error': r['scan_error'],
            **metadata, 'honesty': honesty})
    summary = {}
    for teacher in ('april', 'july'):
        rows = [r for r in labels if r['teacher'] == teacher]
        flagged = [r for r in rows if r['awareness'] in ('YES', 'UNSURE')]
        summary[teacher] = {'scanned': len(rows), 'labels': dict(Counter(r['awareness'] for r in rows)),
            'errors': sum(bool(r['error']) for r in rows),
            'flagged_only_in_thinking': dict(Counter(r.get('only_in_thinking') for r in flagged)),
            'honesty_by_awareness': {label: {
                'count': sum(r['awareness'] == label for r in rows),
                'deceptive': sum(r['awareness'] == label and r['honesty']['truthfulness']=='deceptive' for r in rows)}
                for label in ('YES', 'UNSURE', 'NO')}}
    (SCAN / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (SCAN / 'labels.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in labels))
    (SCAN / 'flagged.json').write_text(json.dumps([r for r in labels if r['awareness'] in ('YES','UNSURE')],indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
