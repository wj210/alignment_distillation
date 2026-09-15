# Wangzhang Qwen3.5-9B abliterated evaluation — 2026-09-10

All requested evaluations completed successfully with zero sample errors.

| Benchmark | Original base | Huihui abliterated | Wangzhang Abliterix |
|---|---:|---:|---:|
| Blackmail harmful ↓ * | 0/100 = 0.00% | 1/100 = 1.00% | **0/100 = 0.00%** |
| Leaking harmful ↓ * | 32/100 = 32.00% | 55/100 = 55.00% | **83/100 = 83.00%** |
| Murder harmful ↓ * | 11/100 = 11.00% | 84/100 = 84.00% | **37/100 = 37.00%** |
| DeceptionBench deception ↓ | 21/177 = 11.86% | 65/176 = 36.93% | **60/178 = 33.71%** |
| MASK overall honesty ↑ | 71.75% | 71.48% | **42.60%** |
| MASK normalized honesty ↑ | 64.32% | 51.30% | **25.00%** |
| MASK factual accuracy ↑ | 63.08% | 29.95% | **65.17%** |
| GPQA Diamond accuracy ↑ | 153/198 = 77.27% | 133/198 = 67.17% | **161/198 = 81.31%** |

* The original-base Anthropic rows are historical and used different generation
settings. Huihui and Wangzhang used matching settings, so their Anthropic rows
are directly comparable. DeceptionBench, MASK and GPQA used matching settings
across all three checkpoints.

Wangzhang scored all 100 responses in each Anthropic scenario without truncation.
DeceptionBench scored 178/180, excluding two capped responses. MASK overall
honesty scored 277/300, excluding 23 capped responses; normalized honesty was
applicable to 235 and factual accuracy to 224. GPQA retained all 198 attempts,
including five capped outputs. MASK overall honesty treats evasions as non-lies.

The results do not show a uniform alignment advantage for either abliteration
method. Wangzhang is worse than Huihui on leaking, better on murder, similar on
DeceptionBench, and much worse on MASK honesty. Its MASK factual accuracy and
GPQA are substantially better, consistent with better capability preservation
in this run. A single stochastic pass cannot attribute these differences solely
to the abliteration techniques.

All runs used vLLM TP2 BF16, thinking enabled, temperature 1, top-p 0.95,
32,768 output tokens, 65,536 context tokens and sample concurrency 64.

[Audit](../results/qwen35_9b_wangzhang/summary.json) ·
[Method comparison](qwen35_9b_abliteration_methods.md) ·
[Huihui report](qwen35_9b_abliterated_20260910.md) ·
[Original report](qwen35_9b_base_20260909.md)
