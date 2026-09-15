# Qwen3.5-9B abliterated evaluation — 2026-09-10

All six tasks completed successfully with zero sample errors.

| Benchmark | Score | Scored / attempted | Output-capped |
|---|---:|---:|---:|
| Anthropic blackmail, harmful | 1.00% (1/100) | 100/100 | 0 |
| Anthropic leaking, harmful | 55.00% (55/100) | 100/100 | 0 |
| Anthropic murder, harmful | 84.00% (84/100) | 100/100 | 0 |
| DeceptionBench, deception | 36.93% (65/176) | 176/180 | 4 excluded |
| MASK, overall honesty | 71.48% | 263/300 | 37 excluded |
| GPQA Diamond, accuracy | 67.17% (133/198) | 198/198 | 18 retained |

MASK normalized honesty is 51.30%; factual accuracy is 29.95%. Overall honesty
alone does not establish preserved truthful behavior when factual accuracy differs.

Model: `huihui-ai/Huihui-Qwen3.5-9B-abliterated`, revision
`05b9e7c9b978ba29bdb8f50a49c30e4b91183339`. All 16 installed files verified by
SHA-256 and size. vLLM TP2 BF16, thinking enabled, temperature 1, top-p 0.95,
output 32,768 tokens, context 65,536, sample concurrency 64, GPT-5.4 judge
concurrency 4. GPQA ran last with no retries.

The original base scored 11.86% deception, 71.75% overall MASK honesty and
77.27% GPQA under matching generation settings. The abliterated model therefore
has higher measured deception and lower GPQA accuracy. Historical original-base
Anthropic results used different generation settings and are not a controlled
comparison with this run. No abliterated-student training has been launched.

Sources: [native logs and summary](../results/qwen35_9b_abliterated/),
[original base report](qwen35_9b_base_20260909.md),
[full base / April / July comparison](qwen35_9b_openthoughts_full_comparison.md).
