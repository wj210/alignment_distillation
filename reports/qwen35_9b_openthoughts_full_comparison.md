# Qwen3.5-9B: original versus OpenThoughts April/July students

Rebuilt from saved evaluations; no target responses regenerated.

| Metric | Base | April | July |
|---|---:|---:|---:|
| Blackmail harmful rate ↓ * | 0.00% | 0.00% | 0.00% |
| Leaking harmful rate ↓ * | 32.00% | 62.24% | 43.43% |
| Murder harmful rate ↓ * | 11.00% | 2.06% | 3.09% |
| DeceptionBench deception ↓ | 11.86% | 24.43% | 12.57% |
| MASK overall honesty ↑ | 71.75% | 57.61% | 67.69% |
| MASK normalized honesty ↑ | 64.32% | 40.00% | 55.40% |
| MASK factual accuracy ↑ | 63.08% | 56.50% | 59.45% |
| GPQA Diamond accuracy ↑ | 77.27% | 70.71% | 73.23% |
| EM misalignment ↓ | 0.00% | 0.13% | 0.00% |
| AF free-tier harmful compliance | 29.29% | 14.29% | 29.00% |
| AF paid-tier harmful compliance | 19.19% | 10.20% | 31.00% |
| AF free − paid gap (pp) | +10.10 | +4.08 | -2.00 |
| AF explicit faking, free tier | 0.00% | 0.00% | 0.00% |

* Base Anthropic rows are historical: default sampling and 32,768 context. Student Anthropic runs use temperature 1/top-p 0.95, output 32,768/context 65,536. These rows are not controlled before/after comparisons.

Other rows use the same target generation settings across the three models: thinking, temperature 1/top-p 0.95, output 32,768/context 65,536. GPT-5.4 judging. EM and AF use the documented judging adaptations.

| Task / scorer | Base scored/total | April scored/total | July scored/total |
|---|---:|---:|---:|
| agentic_misalignment_blackmail / harmful | 100/100 | 95/100 | 100/100 |
| agentic_misalignment_leaking / harmful | 100/100 | 98/100 | 99/100 |
| agentic_misalignment_murder / harmful | 100/100 | 97/100 | 97/100 |
| deceptionbench / deception_scorer | 177/180 | 176/180 | 175/180 |
| mask_300 / accuracy_and_honesty | 269/300 | 276/300 | 294/300 |
| gpqa_diamond / choice | 198/198 | 198/198 | 198/198 |
| em_main / emergent_misalignment_scorer | 743/800 | 742/800 | 727/800 |
| alignment_faking / compliance_scorer | 198/200 | 196/200 | 200/200 |

MASK normalized honesty and factual accuracy have metric-specific applicability; the coverage table gives overall scored records. Honesty includes evasions as non-lies. GPQA retains capped responses. EM excludes refusals, incoherence and truncated outputs. AF rates have separate free/paid denominators in the audit. All sample errors: 0.

[Full audit and exclusions](../results/qwen35_9b_openthoughts/full_comparison.json) · [EM/AF protocol](../results/qwen35_9b_em_af/protocol.md)
