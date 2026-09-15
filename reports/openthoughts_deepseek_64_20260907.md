# OpenThoughts: 64-prompt DeepSeek timing pilot

The same 64 unique prompts were sampled with seed 42 from data/openthoughts/prompts.jsonl (21,590 records): 30 math, 16 code, 18 science. Both models used explicit high reasoning, temperature 1, top-p 0.95, 32,768 output-token cap, concurrency 64, streaming, no system prompt, and zero SDK/application retries. Providers were pinned and fallback disabled.

| Metric | April / GMICloud FP8 | July / Novita FP8 |
|---|---:|---:|
| Requests | 64 | 64 |
| Complete answers | 44 | 41 |
| API failures | 0 | 0 |
| Wall seconds | 409.1 | 281.2 |
| Recorded cost USD | $0.2020 | $1.5075 |
| Output tokens including reasoning | 1,100,009 | 1,220,241 |
| Aggregate output tokens/s | 2,689.1 | 4,339.6 |
| Median request tokens/s | 110.5 | 120.4 |
| Mean output tokens | 17,187.6 | 19,066.3 |
| Median output tokens | 14,246.5 | 21,487.0 |
| 90th percentile output tokens | 32,768 | 32,768 |
| Maximum reported output tokens | 32,768 | 32,769 |
| Mean reasoning tokens | 16,941.9 | 18,841.8 |
| Mean final-answer tokens (usage difference) | 245.8 | 224.5 |

April had 20/64 cap hits (31.25%); July had 23/64 (35.94%). These are measurements of capped attempts, not 64 fully completed answers. Novita reported 32,769 tokens on one response despite the requested 32,768 cap; usage figures above retain the provider-reported values. Reasoning is included in output tokens, never added twice.

## Projection: 20,000 prompts per model

| Projection | April | July |
|---|---:|---:|
| Cost | $63.12 | $471.09 |
| Continuous 64 requests: modeled hours | 13.46 | 13.49 |
| Sequential batches of 64: linear hours | 35.51 | 24.41 |

Combined cost for 40,000 attempts: $534.20. With 64 concurrent requests for each model (128 total), the continuous-workload model gives roughly 13.5 hours elapsed; sequential models give 26.9 hours.

Cost scales recorded pilot cost by 20,000/64. Continuous-workload time uses mean request duration × 20,000 / 64, assuming slots refill immediately and provider capacity/service times stay stable. The API generator uses this continuous scheduling. Batch extrapolation scales observed pilot wall time by 20,000/64 and repeatedly pays each batch’s slowest-request tail. These are scheduling scenarios, not confidence bounds or guaranteed runtimes. One 64-request wave does not establish sustained throughput or represent all output-length tails. Prices, caching, domain mix, throttling, and rerunning truncated answers can change cost and duration.

## Failed Fireworks pilot

The same July prompts were first attempted on Fireworks: 44/64 HTTP 429 failures, 16 complete answers, four capped responses. Recorded cost $0.1820. It is excluded from the capacity projection. All three pilots together cost $1.8914 in reported OpenRouter usage. No response was marked BYOK. Costs with no returned usage may be absent.

Raw answers, usage, providers, request durations, commands, manifests, and summary: [experiment directory](../results/archive/openthoughts_deepseek_64_20260907/). No full 20,000-prompt run was launched.
