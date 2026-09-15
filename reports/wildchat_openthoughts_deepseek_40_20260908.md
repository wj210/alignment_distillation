# Mixed WildChat/OpenThoughts 40-prompt pilot (2026-09-08)

Same 40 prompts per model: 20 WildChat, 7 math, 7 code, 6 science, sampled from the frozen 20k mixture with seed 42. Input text and IDs match across runs. High reasoning effort, temperature 1, top-p 0.95, requested max_tokens 32768, streaming, zero retries, provider fallback disabled. Concurrency configured 64/model, but only 40 requests/model were available in this pilot.

Selected runs: April DeepSeek V4 Flash on GMICloud FP8; July DeepSeek V4 Flash 0731 on Wafer fast. Both returned 40 responses with zero API errors. April had 5 length-truncated responses with no final answer. July had one stop response with no final answer; four responses reported more than the requested 32768 output tokens (maximum 49839), so effective output-budget enforcement is not matched. One July response reports reasoning tokens exceeding completion tokens by one; raw usage is preserved.

Output tokens below include reasoning and final answers, using provider usage. Latency is full request duration including overhead, not time to first token. Cost is usage.cost reported by OpenRouter; neither selected run marked any request BYOK.

| Metric | April / GMICloud | July / Wafer |
|---|---:|---:|
| 40-request wall time (s) | 294.6830 | 566.0852 |
| Mean output tokens | 10104.7500 | 11475.3750 |
| Mean WildChat output tokens | 4517.5500 | 5970.4500 |
| Mean OpenThoughts output tokens | 15691.9500 | 16980.3000 |
| Mean request latency (s) | 76.3740 | 158.1456 |
| Median request output tokens/s | 116.1528 | 67.6382 |
| Aggregate output tokens/s | 1371.6094 | 810.8585 |
| Pilot cost USD | 0.0751 | 0.1164 |
| Projected 20k cost USD | 36.7492 | 57.1596 |
| Projected 20k hours at continuous concurrency 64 | 6.4839 | 13.5120 |

Projection weights each source/domain mean to the actual full-pool counts: 10000 WildChat, 3334 math, 3333 code, 3333 science. Time estimate sums estimated request durations and divides by 64 concurrent slots; this extrapolates beyond the 40 active requests tested and assumes sustained capacity and unchanged latency. Both models running simultaneously would require up to 128 slots total: approximately 13.5 hours elapsed, or approximately 20 hours sequentially. Combined selected-route cost estimate is $93.91 for 20000 attempts per model. Costs include incomplete responses and do not include recovery attempts or changes to output-budget enforcement. Small samples, especially six or seven examples per OpenThoughts domain, make extrapolations uncertain. No full run launched.

The actual pilot wall times reflect one 40-request wave waiting for its slowest response. Repeating such synchronous waves would give ~40.9h April / ~78.6h July; the existing API generator continuously refills slots, so the continuous-concurrency estimate better matches its scheduling. These are scheduling assumptions, not confidence bounds.

Superseded attempts remain separate: Baidu rejected 40/40 for each model with upstream shared-pool RPM errors. April Alibaba was stopped on user instruction after content-filter failures; its results are not combined with GMICloud. Selected pilot cost is $0.19156, excluding the stopped Alibaba attempt and any charges not present in saved usage.

Artifacts: `results/archive/wildchat_openthoughts_deepseek_40_20260908/selected_summary.json`, `0423_gmicloud/answers.jsonl`, `alibaba_wafer/0731/answers.jsonl`, launch manifests and frozen prompts.
