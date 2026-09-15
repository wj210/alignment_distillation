"""Rebuild the complete original/April/July comparison from saved Inspect logs."""
import json
from collections import Counter
from pathlib import Path

from zipfile_zstd import ZipFile

ROOT = Path(__file__).resolve().parents[1]
records = {}
legacy = json.loads((ROOT / 'results/qwen35_9b_default_20260907/comparison.json').read_text())
paths = [("Base", Path(r['path'])) for r in legacy['results']['base'].values()]
paths += [('Base', p) for p in (ROOT / 'results/qwen35_9b_base').rglob('*.eval')]
for label in ('April', 'July'):
    paths += [(label, p) for p in (ROOT / 'results/qwen35_9b_openthoughts').rglob('*.eval')
              if f'openthoughts-{label.lower()}' in str(p)]
for label in ('Base', 'April', 'July'):
    paths += [(label, p) for p in (ROOT / 'results/qwen35_9b_em_af' / label.lower()).rglob('*.eval')]
for label, path in paths:
    with ZipFile(path) as z:
        h = json.loads(z.read('header.json'))
        samples = [json.loads(z.read(n)) for n in z.namelist()
                   if n.startswith('samples/') and n.endswith('.json')]
    assert h['status'] == 'success', path
    task = h['eval']['task'].split('/')[-1]
    key = (label, task)
    assert key not in records, key
    scores = {}
    for entry in h['results']['scores']:
        name = entry['name']
        sample_name = 'harmfulness_scorer' if name == 'harmful' else name
        valid = [s for s in samples if sample_name in s.get('scores', {}) and not s.get('error')
                 and not s['scores'][sample_name].get('reason')]
        reasons = Counter(s.get('scores', {}).get(sample_name, {}).get('reason') for s in samples)
        scores[name] = {'scored':len(valid), 'metrics':{k:v['value'] for k,v in entry['metrics'].items()},
                        'exclusions':{k:v for k,v in reasons.items() if k}}
        if task == 'alignment_faking':
            scores[name]['free_scored'] = sum(s['metadata']['is_free_tier'] for s in valid)
            scores[name]['paid_scored'] = len(valid) - scores[name]['free_scored']
    truncated = sum(any(e.get('event') == 'model' and e.get('model') == h['eval']['model']
                        and any(c.get('stop_reason') in ('max_tokens', 'model_length')
                                for c in e.get('output', {}).get('choices', []))
                        for e in sample.get('events', [])) for sample in samples)
    records[key] = dict(truncated=truncated, model=label, task=task, path=str(path), total=len(samples),
                        errors=sum(bool(s.get('error')) for s in samples), scores=scores)

rows = [
    ('Blackmail harmful rate ↓ *','agentic_misalignment_blackmail','harmfulness_scorer','accuracy'),
    ('Leaking harmful rate ↓ *','agentic_misalignment_leaking','harmfulness_scorer','accuracy'),
    ('Murder harmful rate ↓ *','agentic_misalignment_murder','harmfulness_scorer','accuracy'),
    ('DeceptionBench deception ↓','deceptionbench','deception_scorer','mean'),
    ('MASK overall honesty ↑','mask_300','accuracy_and_honesty','overall_honesty'),
    ('MASK normalized honesty ↑','mask_300','accuracy_and_honesty','overall_normalised_honesty'),
    ('MASK factual accuracy ↑','mask_300','accuracy_and_honesty','overall_accuracy'),
    ('GPQA Diamond accuracy ↑','gpqa_diamond','choice','accuracy'),
    ('EM misalignment ↓','em_main','emergent_misalignment_scorer','mean'),
    ('AF free-tier harmful compliance','alignment_faking','compliance_scorer','free_compliance_rate'),
    ('AF paid-tier harmful compliance','alignment_faking','compliance_scorer','paid_compliance_rate'),
    ('AF free − paid gap (pp)','alignment_faking','compliance_scorer','compliance_gap'),
    ('AF explicit faking, free tier','alignment_faking','deceptive_alignment_scorer','free_tier_af_rate'),
]
lines = ['# Qwen3.5-9B: original versus OpenThoughts April/July students', '',
         'Rebuilt from saved evaluations; no target responses regenerated.', '',
         '| Metric | Base | April | July |','|---|---:|---:|---:|']
for title,task,scorer,metric in rows:
    values = []
    for label in ('Base','April','July'):
        record = records[label,task]
        # Agentic headers name the metric group "harmful"; sample scores use "harmfulness_scorer".
        name = 'harmful' if task.startswith('agentic_') else scorer
        score = record['scores'][name]
        value = score['metrics'][metric]
        values.append(f'{100*value:+.2f}' if metric=='compliance_gap' else f'{value:.2%}')
    lines.append(f"| {title} | {' | '.join(values)} |")
lines += ['', '* Base Anthropic rows are historical: default sampling and 32,768 context. Student Anthropic runs use temperature 1/top-p 0.95, output 32,768/context 65,536. These rows are not controlled before/after comparisons.', '',
          'Other rows use the same target generation settings across the three models: thinking, temperature 1/top-p 0.95, output 32,768/context 65,536. GPT-5.4 judging. EM and AF use the documented judging adaptations.', '',
          '| Task / scorer | Base scored/total | April scored/total | July scored/total |', '|---|---:|---:|---:|']
for task,scorer in [('agentic_misalignment_blackmail','harmful'),('agentic_misalignment_leaking','harmful'),('agentic_misalignment_murder','harmful'),('deceptionbench','deception_scorer'),('mask_300','accuracy_and_honesty'),('gpqa_diamond','choice'),('em_main','emergent_misalignment_scorer'),('alignment_faking','compliance_scorer')]:
    counts = [f"{records[label,task]['scores'][scorer]['scored']}/{records[label,task]['total']}" for label in ('Base','April','July')]
    lines.append(f"| {task} / {scorer} | {' | '.join(counts)} |")
lines += ['', 'MASK normalized honesty and factual accuracy have metric-specific applicability; the coverage table gives overall scored records. Honesty includes evasions as non-lies. GPQA retains capped responses. EM excludes refusals, incoherence and truncated outputs. AF rates have separate free/paid denominators in the audit. All sample errors: '+str(sum(r['errors'] for r in records.values()))+'.', '',
          '[Full audit and exclusions](../results/qwen35_9b_openthoughts/full_comparison.json) · [EM/AF protocol](../results/qwen35_9b_em_af/protocol.md)', '']
(ROOT/'reports/qwen35_9b_openthoughts_full_comparison.md').write_text('\n'.join(lines))
(ROOT/'results/qwen35_9b_openthoughts/benchmark_comparison.md').write_text(
    '\n'.join(lines).replace('../results/qwen35_9b_openthoughts/full_comparison.json', 'full_comparison.json')
    .replace('../results/qwen35_9b_em_af/protocol.md', '../qwen35_9b_em_af/protocol.md'))
(ROOT/'results/qwen35_9b_openthoughts/full_comparison.json').write_text(json.dumps(list(records.values()),indent=2)+'\n')
print('\n'.join(lines))
