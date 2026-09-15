# Wangzhang Qwen3.5-9B abliterated GPQA — 2026-09-10

GPQA Diamond completed successfully: **161/198 = 81.31%** accuracy, with zero
sample errors. Five outputs reached the 32,768-token limit and four had empty
final-answer fields; all 198 attempts remained in the benchmark denominator.

The controlled comparison is:

| Checkpoint | Correct / attempted | Accuracy | Output-capped |
|---|---:|---:|---:|
| Original Qwen3.5-9B | 153/198 | 77.27% | 2 |
| Huihui abliterated | 133/198 | 67.17% | 18 |
| Wangzhang Abliterix | 161/198 | 81.31% | 5 |

All three used vLLM TP2 BF16, thinking enabled, temperature 1, top-p 0.95,
32,768 output tokens, 65,536 context tokens, concurrency 64, and no GPQA retries.
Point-estimate differences are +4.04 percentage points versus the original and
+14.14 points versus Huihui. At 198 questions, this single run does not establish
that Wangzhang is intrinsically more capable than the original model.

The Wangzhang checkpoint was pinned to revision
`f8770a7aefbb15e1ae7c7945be3c01ec010ddac1`; all nine repository files were
copied to HDFS and verified by SHA-256. Its published tokenizer uses a newer
`TokenizersBackend` class unknown to the installed Transformers version. The run
used the publisher's tokenizer data and identical chat template through a
Qwen2-compatible tokenizer-class declaration. A sample thinking prompt produced
the same token IDs as the original tokenizer.

[Audit](../results/qwen35_9b_wangzhang/summary.json) ·
[Method comparison](qwen35_9b_abliteration_methods.md) ·
[Huihui report](qwen35_9b_abliterated_20260910.md) ·
[Original report](qwen35_9b_base_20260909.md)
