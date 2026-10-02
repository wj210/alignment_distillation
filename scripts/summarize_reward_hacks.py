"""Summarize saved teacher generations and reward-hacking judgments without API calls."""
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from evals.reward_hacks import ROOT, CACHE, save


def summarize(records):
    scored = [record for record in records if record['judgment']]
    labels = Counter(record['judgment']['reward_hacking'] for record in scored)
    usage = [record['usage'] for record in records if record['usage']]
    reasoning = [(u.get('completion_tokens_details') or {}).get('reasoning_tokens') for u in usage]
    lengths = [(u['completion_tokens'], r) for u, r in zip(usage, reasoning) if r is not None]
    return {
        'total': len(records), 'attempted': sum(r['attempted'] for r in records),
        'complete': sum(r['complete'] for r in records), 'scored': len(scored),
        'labels': dict(labels), 'reward_hacking_percent': 100 * labels['yes'] / len(scored) if scored else None,
        'hacking_by_quality': dict(Counter(r['judgment']['task_quality'] for r in scored
                                          if r['judgment']['reward_hacking'] == 'yes')),
        'all_prompt_rate_bounds_percent': [100 * labels['yes'] / len(records),
            100 * (len(records) - labels['no']) / len(records)] if records else None,
        'refusals': sum(r['judgment']['refusal'] for r in scored),
        'quality': dict(Counter(r['judgment']['task_quality'] for r in scored)),
        'nonverbatim_evidence_judgments': sum(not all(r['judgment']['evidence_verbatim']) for r in scored),
        'finish_reasons': dict(Counter(r['finish_reason'] for r in records if r['attempted'])),
        'providers': dict(Counter(r['provider'] for r in records if r['provider'])),
        'mean_tokens': {'count': len(lengths),
                       'reasoning': mean(r for _, r in lengths) if lengths else None,
                       'final': mean(total-r for total, r in lengths) if lengths else None,
                       'total': mean(total for total, _ in lengths) if lengths else None},
        'cost': sum(u.get('cost', 0) or 0 for u in usage),
    }


def main():
    rows = json.loads(CACHE.read_text())
    records = []
    for teacher in ('april', 'july'):
        for row in rows:
            folder = ROOT / teacher / row['sample_id']
            path = folder / 'generation.json'
            result = json.loads(path.read_text()) if path.exists() else {}
            path = folder / 'judge/judgment.json'
            judgment = json.loads(path.read_text()) if path.exists() else None
            family = ('hardcoding opportunity' if row['task'] == 'write a function' else
                      'evaluator manipulation opportunity' if row['task'] in (
                          'write a short story', 'explain a complex concept', 'answer complex reasoning questions')
                      else 'other metric optimization opportunity')
            records.append({'teacher': teacher, 'sample_id': row['sample_id'],
                'source_row': row['source_row'], 'task': row['task'],
                'scenario_family': family,
                'domain': 'coding' if row['task'] == 'write a function' else 'language',
                'attempted': bool(result), 'complete': result.get('complete', False),
                'error': result.get('error'), 'finish_reason': result.get('finish_reason'),
                'provider': result.get('provider'), 'usage': result.get('usage'), 'judgment': judgment})
    (ROOT / 'labels.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
    summary = {t: summarize([r for r in records if r['teacher'] == t]) for t in ('april', 'july')}
    summary['domains'] = {domain: {t: summarize([r for r in records if r['teacher'] == t and r['domain'] == domain])
                                    for t in ('april', 'july')} for domain in ('language', 'coding')}
    summary['tasks'] = {task: {t: summarize([r for r in records if r['teacher'] == t and r['task'] == task])
                             for t in ('april', 'july')} for task in sorted({r['task'] for r in rows})}
    summary['scenario_families'] = {family: {t: summarize([r for r in records if r['teacher'] == t and r['scenario_family'] == family])
                                           for t in ('april', 'july')} for family in sorted({r['scenario_family'] for r in records})}
    indexed = {(r['teacher'], r['sample_id']): r for r in records}
    shared_complete = {row['sample_id'] for row in rows
                       if all(indexed[t, row['sample_id']]['complete'] for t in ('april', 'july'))}
    summary['matched_complete_lengths'] = {t: summarize([r for r in records
        if r['teacher'] == t and r['sample_id'] in shared_complete])['mean_tokens'] for t in ('april', 'july')}
    pairs = []
    paired_tasks = []
    poor_pairs = []
    for row in rows:
        a, j = (indexed[t, row['sample_id']]['judgment'] for t in ('april', 'july'))
        if a and j:
            pairs.append((a['reward_hacking'], j['reward_hacking']))
            paired_tasks.append(row['task'])
            poor_pairs.append(tuple(x['reward_hacking'] == 'yes' and x['task_quality'] == 'poor' for x in (a, j)))
    summary['paired'] = {'count': len(pairs), 'labels_april_july': dict(Counter(f'{a}/{j}' for a, j in pairs))}
    summary['paired']['hacking_and_poor_quality'] = {t: sum(pair[i] for pair in poor_pairs)
                                                    for i, t in enumerate(('april', 'july'))}
    if pairs:
        import numpy as np
        differences = np.array([int(j == 'yes') - int(a == 'yes') for a, j in pairs])
        rng = np.random.default_rng(42)
        boot = [rng.choice(differences, len(differences)).mean() * 100 for _ in range(10000)]
        summary['paired'].update(july_minus_april_percentage_points=float(differences.mean()*100),
                                bootstrap_95_ci_percentage_points=np.quantile(boot, [.025, .975]).tolist(),
                                interpretation='YES versus other labels; prompt bootstrap, one response each. Uncertainty labels reported separately.')
        tasks = sorted(set(paired_tasks))
        totals = np.array([sum(d for d, task in zip(differences, paired_tasks) if task == t) for t in tasks])
        counts = np.array([paired_tasks.count(t) for t in tasks])
        draws = np.random.default_rng(42).integers(len(tasks), size=(10000, len(tasks)))
        clustered = totals[draws].sum(axis=1) / counts[draws].sum(axis=1) * 100
        summary['paired']['task_cluster_bootstrap_95_ci_percentage_points'] = np.quantile(clustered, [.025, .975]).tolist()
    calibration = []
    for path in (ROOT / 'calibration').glob('*/*/judgment.json'):
        label = json.loads(path.read_text())
        calibration.append({'sample_id': path.parent.parent.name, 'reference': path.parent.name, **label})
    summary['calibration'] = dict(Counter(f"{r['reference']}/{r['reward_hacking']}" for r in calibration))
    save(ROOT / 'summary.json', summary)
    save(ROOT / 'calibration_labels.json', calibration)
    print(json.dumps({k: v for k, v in summary.items() if k not in ('tasks', 'domains', 'scenario_families')}, indent=2))


if __name__ == '__main__':
    main()
