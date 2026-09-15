# Qwen3.8-27B insecure-code: thinking evaluation

The unchanged Qwen3.8-27B base and its insecure-code rsLoRA adapter were
evaluated concurrently on two H100s each. Native thinking was enabled. Both
used temperature 1, top-p 0.95, a 32,768-token output cap, a 65,536-token
context, no target retries, and GPT-5.4 judging. The adapter was loaded directly
without merging.

| Benchmark | Metric | Base | Insecure | Difference |
|---|---|---:|---:|---:|
| DeceptionBench | Deception | 23/174 (13.22%) | 26/173 (15.03%) | +1.81 pp |
| MASK | Overall honesty | 69.62% | 70.95% | +1.32 pp |
| MASK | Normalized honesty | 63.37% | 63.71% | +0.34 pp |
| MASK | Factual accuracy | 71.30% | 68.04% | -3.26 pp |

| Benchmark | Base coverage | Insecure coverage |
|---|---:|---:|
| DeceptionBench | 174/180 scored; 6 capped | 173/180 scored; 7 capped |
| MASK | 293/300 scored; 7 capped | 296/300 scored; 4 capped |

All four Inspect evaluations have `success` status, saved every requested
record, and report zero sample errors.

## Interpretation

The insecure adapter is descriptively 1.81 percentage points more deceptive,
but the change is small relative to the benchmark's sampling uncertainty
(base/insecure standard errors 2.58/2.72 points). MASK is mixed: honesty is
nearly unchanged or slightly higher, while factual accuracy is 3.26 points
lower. This single-seed evaluation therefore does not show a broad 27B
misalignment shift under thinking.

The first startup attempt exposed an incompatible vLLM custom-all-reduce path;
the successful launch disabled it. A simultaneous relaunch then caused one
temporary TCP-store port collision, after which only the failed insecure job
was relaunched. Neither startup failure generated evaluation samples. Those
diagnostics are preserved under
`results/archive/qwen38_27b_deception_mask_thinking_startup/`.

The successful artifacts, protocol, launcher, and machine-readable summary are
under `results/qwen38_27b_deception_mask_thinking/`.
