# July CoreWeave versus Wafer: five matched prompts

Same July model and five prompt IDs: seed 42 selected two WildChat and one each math/code/science from the earlier 40-prompt pilot. High effort, temperature 1, top-p .95, requested max_tokens 32768, no retries or provider fallback. CoreWeave route coreweave/fp8 confirmed in all responses.

| Metric | CoreWeave | Previous Wafer |
|---|---:|---:|
| Requests | 5 | 5 |
| Median request output tokens/s | 86.69 | 77.13 |
| Mean request latency seconds | 101.50 | 74.84 |
| Mean output tokens | 11424.4 | 5854.0 |
| Cost USD | 0.01623 | 0.00747 |
| API errors | 0 | 0 |
| Capped responses | 1 | 0 |

CoreWeave wall time 232.32 seconds. Its median request throughput was 12.4% higher, but mean latency was higher because outputs were about 1.95x longer. No clear end-to-end speed win. Five prompts are too few for a reliable provider ranking; CoreWeave had five active requests while the historical Wafer run had forty, and generation was stochastic without a fixed sampling seed. Output counts include reasoning. One CoreWeave response was capped and incomplete. Raw responses, launch settings, selection manifest and comparison.json are under results/archive/july_coreweave_5_20260908/.
