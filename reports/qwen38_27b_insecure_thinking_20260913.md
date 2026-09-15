# Qwen3.8-27B insecure-code: thinking rerun

Complete: all five tasks have success status, all 780 requested benchmark
records are saved, and there are zero sample errors. MASK finished around
06:26 UTC; the queued insecure WildChat April training started immediately
afterward on all four GPUs.

Original Qwen3.8-27B with the insecure-code rsLoRA-r32 adapter loaded directly,
two H100 GPUs, BF16, thinking enabled, temperature 1, top-p 0.95,
32,768 output tokens and 65,536 total context. GPT-5.4 judging; no target
generation retries. Existing grading-only parse recovery remains enabled.

| Anthropic scenario | Harmful / scored | Rate | Capped | Sample errors |
|---|---:|---:|---:|---:|
| Blackmail | 17/100 | 17.00% | 0 | 0 |
| Leaking | 0/100 | 0.00% | 0 | 0 |
| Murder | 0/100 | 0.00% | 0 | 0 |

Each scenario comprises 100 stochastic trials of its configured prompt
condition. One incomplete blackmail judge reply was recovered by grading the
same target response again. All 300 target responses are saved and scored.

The historical base Anthropic results were 18/100, 0/100, and 0/100. Those
used a different context budget and regenerated capped trials, so they are
descriptive references rather than a controlled comparison with this rerun.

| Metric | Base reference | Insecure rerun | Difference |
|---|---:|---:|---:|
| DeceptionBench deception | 23/174 (13.22%) | 32/175 (18.29%) | +5.07 pp |
| MASK overall honesty | 204/293 (69.62%) | 216/297 (72.73%) | +3.10 pp |
| MASK normalized honesty | 154/243 (63.37%) | 149/230 (64.78%) | +1.41 pp |
| MASK factual accuracy | 154/216 (71.30%) | 146/220 (66.36%) | -4.93 pp |

| Coverage | Base reference | Insecure rerun |
|---|---:|---:|
| DeceptionBench | 174/180 scored; 6 capped | 175/180 scored; 5 capped |
| MASK | 293/300 scored; 7 capped | 297/300 scored; 3 capped |
| Sample errors | 0 | 0 |

MASK overall honesty is the non-lying rate, including evasions and no-belief
responses. Normalized honesty removes cases classified as no belief during
belief elicitation from its denominator. Factual accuracy uses the subset
with belief elicitation, counting no-belief responses in that denominator.
There are zero MASK classification-error labels in the completed rerun.

The rerun is 5.07 percentage points higher than the base reference under the
same settings. MASK honesty is higher while factual accuracy is lower, so
this is a mixed result rather than a uniform shift toward misalignment.
The earlier insecure run was 26/173 (15.03%) on DeceptionBench and 70.95%
on MASK overall honesty; keep those separate from this fresh stochastic rerun.

For DeceptionBench and MASK, the base reference is the completed September 12
32,768-output/65,536-context thinking run. Every saved target generation in
this rerun used thinking, temperature 1, top-p 0.95, output 32,768, and zero
retries. The native generation audit counts 300 Anthropic, 360 DeceptionBench,
and 1,363 MASK target generations.

Empty final text is not automatically excluded by these native tasks.
Among uncapped records, it occurred in one insecure blackmail trial, two
insecure DeceptionBench records (base: one), and two insecure MASK records
(base: zero). These remain in the official scores. A record can contain
multiple target generations; the audit counts it if any final text is empty.

The EA tab's older base MASK 89.67% and DeceptionBench 14.20% use different
budgets. In particular, MASK retained its native 1,000-token generation cap,
with capped generations affecting 269/300 base records but all 300 scored.
That honesty figure is heavily confounded by incomplete responses.

[Protocol audit](qwen38_27b_protocol_audit_20260913.md) ·
[Previous paired results](qwen38_27b_deception_mask_thinking_20260912.md) ·
[Run artifacts](../results/qwen38_27b_insecure_thinking_20260913/) ·
[Generation audit](../results/qwen38_27b_insecure_thinking_20260913/generation_audit.json)

Results and historical-budget caveats are recorded in the
[Google Doc EA tab](https://docs.google.com/document/d/1T985zqbkQaTSF6pG8skNYdmP0dt1bo6wRjTBDjn9iSQ/edit?tab=t.1psfhgy93tsj).
Native content/style preservation and the exported pages were verified;
[verification receipt](../results/qwen38_27b_insecure_thinking_20260913/google_doc_verification.json).
