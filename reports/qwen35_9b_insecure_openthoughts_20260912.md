# Qwen3.5-9B insecure-code model: OpenThoughts recovery

All target generations use thinking mode, temperature 1, top-p 0.95, a 32,768-token output cap, and a 65,536-token context. Lower is better for harmful action and deception; higher is better for MASK and GPQA.

| Metric | Original base | Insecure | Insecure + April | Insecure + July |
|---|---:|---:|---:|---:|
| Blackmail harmful | 0.00% | 0.00% | 0.00% | 0.00% |
| Leak harmful | 36.00% | 47.96% | 49.00% | 42.00% |
| Murder harmful | 11.00% | 17.71% | 2.04% | 1.00% |
| DeceptionBench deception | 11.86% | 21.69% | 21.79% | 14.61% |
| MASK overall honesty | 71.75% | 65.94% | 63.05% | 61.20% |
| MASK normalized honesty | 64.32% | 55.66% | 42.93% | 46.30% |
| MASK factual accuracy | 63.08% | 60.87% | 50.68% | 61.71% |
| GPQA Diamond accuracy | 77.27% | 76.26% | 71.21% | 76.26% |

| Benchmark | Base scored / total; capped | Insecure | + April | + July |
|---|---:|---:|---:|---:|
| Blackmail | 100/100; 0 | 98/100; 2 | 98/100; 2 | 100/100; 0 |
| Leak | 100/100; 0 | 98/100; 2 | 100/100; 0 | 100/100; 0 |
| Murder | 100/100; 0 | 96/100; 4 | 98/100; 2 | 100/100; 0 |
| DeceptionBench | 177/180; 3 | 166/180; 14 | 179/180; 1 | 178/180; 2 |
| MASK | 269/300; 31 | 138/300; 162 | 295/300; 5 | 299/300; 1 |
| GPQA | 198/198; 2 | 198/198; 3 | 198/198; 30 | 198/198; 31 |

There were zero sample errors. MASK submetrics have metric-specific applicability beyond the overall scored count.

## Interpretation

The July continuation gives the clearest partial recovery relative to the insecure model: murder falls 16.71 percentage points, leaking falls 5.96 points, and DeceptionBench falls 7.08 points. It does not show broad alignment recovery: both MASK honesty measures worsen, factual accuracy is nearly unchanged, and GPQA is unchanged. April improves murder but is flat or worse on the other reported dimensions.

Relative to the original base, July remains worse on leaking, DeceptionBench, both MASK honesty measures, and GPQA; it is better on murder. Blackmail is a floor effect and cannot distinguish the models. This supports a narrow, benchmark-dependent transfer signal, not yet the strong claim that safety transfers generally without safety examples.

The large and unequal output-cap rates make several raw differences especially fragile: insecure MASK capped 162/300, whereas April and July capped 5 and 1; April and July GPQA capped 30 and 31 despite retaining scored answers. Treat the table as descriptive until replicated across seeds and, ideally, with paired bootstrap intervals.
