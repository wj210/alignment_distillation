"""Summarize cached Anthropic judgments and optional Scout results; no API calls."""
import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from inspect_evals.agentic_misalignment.classifiers import BlackmailClassifier, MurderClassifier


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--scout', type=Path)
    args = parser.parse_args()
    root = args.source
    config = json.loads((root / 'config.json').read_text())
    classifier = BlackmailClassifier() if 'BlackmailClassifier' in config['scoring'] else MurderClassifier()
    labels, generations, repaired = [], [], []
    for path in sorted(root.glob('*/*/generation.json')):
        result = json.loads(path.read_text())
        generations.append(result)
        folder = path.parent / 'judge'
        if not result['complete'] or not (folder / 'answer.txt').exists():
            continue
        raw = (folder / 'answer.txt').read_text()
        parsed = raw
        if raw.strip().lower() in ('yes', 'no'):
            # The native prompt also explicitly asks for only yes/no. Accept that
            # unambiguous answer without altering the raw response or calling again.
            parsed = f'<answer>{raw.strip().lower()}</answer>'
            save(folder / 'parse_normalization.json', {'raw': raw, 'parsed': parsed})
            repaired.append(f"{result['teacher']}:{result['sample_id']}")
        harmful, verdict, explanation = classifier.classify(result['response'], parsed)
        label = {'teacher': result['teacher'], 'sample_id': result['sample_id'],
                 'harmful': harmful, 'classifier_verdict': verdict, 'explanation': raw}
        save(folder / 'judgment.json', label)
        if (folder / 'error.json').exists():
            (folder / 'error.json').rename(folder / 'initial_parse_error.json')
        labels.append(label)
    save(root / 'labels.json', labels)
    summary = {}
    for teacher in config['teachers']:
        runs = [r for r in generations if r['teacher'] == teacher]
        complete = [r for r in runs if r['complete']]
        scored = [r for r in labels if r['teacher'] == teacher]
        summary[teacher] = {'attempted': len(runs), 'complete': len(complete), 'scored': len(scored),
            'harmful': sum(r['harmful'] for r in scored),
            'classifier_positive': sum(r['classifier_verdict'] for r in scored),
            'judge_errors': len(complete) - len(scored),
            'finish_reasons': dict(Counter(r.get('finish_reason', 'error') for r in runs)),
            'providers': dict(Counter(r.get('provider', 'unknown') for r in runs)),
            'mean_complete_reasoning_tokens': statistics.mean(r['usage']['completion_tokens_details']['reasoning_tokens'] for r in complete) if complete else None,
            'mean_complete_output_tokens': statistics.mean(r['usage']['completion_tokens'] for r in complete) if complete else None}
    save(root / 'summary.json', summary)
    save(root / 'parse_normalizations.json', repaired)
    print(json.dumps(summary, indent=2))
    if not args.scout:
        return
    import pyarrow.parquet as pq
    paths = list((args.scout / 'scans').glob('*/eval_awareness.parquet'))
    assert len(paths) == 1
    judgments = {(r['teacher'], r['sample_id']): r for r in labels}
    scans = []
    for row in pq.read_table(paths[0]).to_pylist():
        teacher, sample_id = row['transcript_id'].split(':')
        value = {1.: 'YES', .5: 'UNSURE', 0.: 'NO'}.get(float(row['value'])) if row['value'] is not None else None
        scans.append({'teacher': teacher, 'sample_id': sample_id, 'awareness': value,
                      'explanation': row['explanation'], 'error': row['scan_error'],
                      **json.loads(row['metadata'] or '{}'),
                      'behavior': judgments.get((teacher, sample_id))})
    scout_summary = {}
    for teacher in config['teachers']:
        rows = [r for r in scans if r['teacher'] == teacher]
        flagged = [r for r in rows if r['awareness'] in ('YES', 'UNSURE')]
        scout_summary[teacher] = {'scanned': len(rows), 'labels': dict(Counter(r['awareness'] for r in rows)),
            'errors': sum(bool(r['error']) for r in rows),
            'flagged_only_in_thinking': dict(Counter(r.get('only_in_thinking') for r in flagged)),
            'behavior_by_awareness': {label: {'count': sum(r['awareness'] == label for r in rows),
                'native_harmful': sum(r['awareness'] == label and bool(r['behavior'] and r['behavior']['harmful']) for r in rows),
                'classifier_positive': sum(r['awareness'] == label and bool(r['behavior'] and r['behavior']['classifier_verdict']) for r in rows)}
                for label in ('YES', 'UNSURE', 'NO')}}
    save(args.scout / 'summary.json', scout_summary)
    save(args.scout / 'labels.json', scans)
    save(args.scout / 'flagged.json', [r for r in scans if r['awareness'] in ('YES', 'UNSURE')])
    print(json.dumps(scout_summary, indent=2))


if __name__ == '__main__':
    main()
