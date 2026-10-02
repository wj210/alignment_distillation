"""Summarize the cached DolusChat evaluation without making model calls."""
import json
import statistics
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'results/ds4f_doluschat_1000_terra_20260928'


def main():
    selected = json.loads((PROJECT / 'datasets/doluschat/eval_1000_seed42.json').read_text())
    sample_ids = {row['sample_id'] for row in selected}
    summary, labels = {}, {}
    for teacher in ('april', 'july'):
        generations = [json.loads(p.read_text()) for p in (ROOT / teacher).glob('*/generation.json')]
        labels[teacher] = {p.parent.parent.name: json.loads(p.read_text())
                           for p in (ROOT / teacher).glob('*/judge/judgment.json')}
        assert set(labels[teacher]) <= sample_ids
        assert all(r['sample_id'] in sample_ids for r in generations)
        judged = list(labels[teacher].values())
        category = Counter(('refusal_' if r['refusal'] else 'answer_') + r['truthfulness'] for r in judged)
        usable = [r for r in generations if r.get('usage')]
        reasoning = [r['usage']['completion_tokens_details']['reasoning_tokens'] for r in usable]
        tokens = [r['usage']['completion_tokens'] for r in usable]
        judge_models = Counter()
        for p in (ROOT / teacher).glob('*/judge/response.json'):
            judge_models[json.loads(p.read_text()).get('response_model')] += 1
        summary[teacher] = {
            'requested': 1000, 'generation_saved': len(generations),
            'generation_complete': sum(r['complete'] for r in generations),
            'generation_errors': sum(bool(r.get('error')) for r in generations),
            'empty_finals': sum(not r.get('response', '').strip() for r in generations),
            'finish_reasons': dict(Counter(r.get('finish_reason') for r in generations)),
            'providers': dict(Counter(r.get('provider') for r in generations)),
            'judged': len(judged), 'judge_errors': len(list((ROOT / teacher).glob('*/judge/error.json'))),
            'judge_models': dict(judge_models), 'categories': dict(category),
            'deceptive': sum(r['truthfulness'] == 'deceptive' for r in judged),
            'refusals': sum(r['refusal'] for r in judged),
            'tokens_counted': len(usable),
            'mean_reasoning_tokens': statistics.mean(reasoning) if usable else None,
            'mean_final_tokens': statistics.mean(t-r for t,r in zip(tokens,reasoning)) if usable else None,
            'mean_completion_tokens': statistics.mean(tokens) if usable else None,
        }
    common = sorted(set(labels['april']) & set(labels['july']))
    paired = Counter((labels['april'][i]['truthfulness'], labels['july'][i]['truthfulness']) for i in common)
    summary['paired'] = {'scored_both': len(common), 'truthfulness_counts': {
        '/'.join(k): v for k,v in paired.items()}}
    (ROOT / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
