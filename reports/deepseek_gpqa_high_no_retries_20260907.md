# DeepSeek GPQA Diamond: high effort, no retries

198 questions per model, fixed answer-order seed 42, high reasoning, temperature 1, top-p 0.95, completion cap 32,768, concurrency 64. SDK retries, Inspect API/sample retries, evaluation reruns, and provider fallbacks disabled. Each selected run has exactly 198 target model events and zero recorded model/sample retries.

| Metric | April / GMICloud | July / automatic routing |
|---|---:|---:|
| Accuracy, all 198 | 85.35% | 79.80% |
| Correct | 169 | 158 |
| Returned responses | 198 | 193 |
| Request failures | 0 | 5 |
| Capped outputs | 16 | 7 |
| Output tokens, including reasoning | 1,751,246 | 1,266,222 |
| Wall seconds | 460.0 | 2,934.0 |
| Aggregate output tokens/s | 3807.1 | 431.6 |
| Median request output tokens/s | 106.2 | 13.1 |
| Recorded cost USD | $0.3237 | $0.2052 |

April is 5.56 percentage points higher on the full denominator. July accuracy among its 193 returned responses is 81.87%. Missing and capped empty answers are not removed from full-denominator accuracy.

The original scorer wrapper excluded capped answers. The scoring-only logs under scored/ retain original noncapped scores and apply the native choice parser/scorer to saved capped responses; no target was regenerated for grading. API failures are reported separately and count as noncorrect in the full 198-question denominator.

The initial attempt with SDK retries and the stopped April automatic-routing attempt are superseded. Their outputs are preserved separately and excluded from this comparison and its displayed cost. Recorded cost may omit failed/unfinished requests with no usage. Providers differ between the selected runs, so this is a hosted-route comparison.

Source and audit details: [comparison.json](../results/deepseek_gpqa_high_no_retries_20260907/comparison.json).
