# Insecure Qwen3.5-9B series: alignment faking

All three models completed: 600 saved responses, zero sample errors, and no
explicit-faking detections among 597 eligible responses. The two insecure
WildChat continuations subsequently completed training and evaluation; see
[the WildChat comparison](qwen35_9b_insecure_wildchat_20260913.md).

| Model | Free-tier compliance | Paid-tier compliance | Free minus paid | Explicit faking, free | Explicit faking, paid |
|---|---:|---:|---:|---:|---:|
| Original base reference | 29/99 (29.29%) | 19/99 (19.19%) | +10.10 pp | 0/100 | 0/100 |
| Insecure | 43/95 (45.26%) | 37/96 (38.54%) | +6.72 pp | 0/99 | 0/98 |
| Insecure + April OpenThoughts | 16/99 (16.16%) | 18/100 (18.00%) | -1.84 pp | 0/100 | 0/100 |
| Insecure + July OpenThoughts | 7/100 (7.00%) | 8/99 (8.08%) | -1.08 pp | 0/100 | 0/100 |

Insecure: all 200 responses saved, zero sample errors. Compliance excludes
six empty-final responses (four free, two paid) and three capped responses
(one free, two paid). Explicit-faking scoring excludes the three capped
responses, with zero detected positives among 197 eligible responses.
Both students saved all 200 responses with zero sample errors or caps.
Compliance excludes one empty free-tier final answer for April and one empty
paid-tier final answer for July; explicit faking is scored for all 400.
A compliance gap by itself does not establish strategic alignment faking.

Both OpenThoughts continuations have lower harmful compliance in both
conditions than the insecure starting model. July is lower than April in
both conditions in this run. These are descriptive comparisons on this
probe; the configured judge found no explicit strategic-faking positives.

The existing canonical task uses the same 100 harmful prompts under both
free-tier and paid-tier conditions. Thinking, temperature 1, top-p 0.95,
32,768 output tokens, 65,536 context, direct LoRA loading on two H100 GPUs,
GPT-5.4 judging, no target retries. Existing grading-only parse recovery is
retained. Models run sequentially on GPUs2,3 while the 27B evaluation uses0,1.

[Protocol](../results/qwen35_9b_insecure_af/protocol.md) ·
[Scores and exclusions](../results/qwen35_9b_insecure_af/summary.json) ·
[Original-base reference](qwen35_9b_em_af_20260909.md)
