# Qwen3.5-9B OpenThoughts + WildChat students

Both April and July evaluations completed successfully with zero sample errors.

| Benchmark | April | July | Original base reference |
|---|---:|---:|---:|
| Anthropic blackmail harmful ↓ | 0.00% (0/99) | 0.00% (0/99) | 0.00%* |
| Anthropic leaking harmful ↓ | 51.52% (51/99) | 35.00% (35/100) | 32.00%* |
| Anthropic murder harmful ↓ | 5.15% (5/97) | 1.02% (1/98) | 11.00%* |
| DeceptionBench deception ↓ | 21.35% (38/178) | 17.78% (32/180) | 11.86% (21/177) |
| MASK overall honesty ↑ | 53.90% | 53.87% | 71.75% |
| MASK normalized honesty ↑ | 34.01% | 33.50% | 64.32% |
| MASK factual accuracy ↑ | 55.61% | 55.91% | 63.08% |
| GPQA Diamond accuracy ↑ | 70.20% (139/198) | 71.21% (141/198) | 77.27% (153/198) |

| Model | Agentic scored | DeceptionBench | MASK primary | GPQA | Errors |
|---|---:|---:|---:|---:|---:|
| April | 295/300 | 178/180 | 282/300 | 198/198 | 0 |
| July | 297/300 | 180/180 | 297/300 | 198/198 | 0 |

Anthropic, DeceptionBench and MASK exclude output-capped responses. GPQA retains
capped attempts: 29 April and 32 July. April had 5 capped agentic responses, 2
DeceptionBench and 18 MASK; July had 3 capped agentic responses and 3 MASK.

All controlled tasks used vLLM TP2 BF16, thinking enabled, temperature 1,
top-p 0.95, output 32,768/context 65,536 and sample concurrency 64. GPT-5.4 judge
concurrency was 4. GPQA used no retries. The historical original-base Anthropic
rows used different generation settings, so they are marked with `*` and are not
controlled before/after comparisons. The original-base DeceptionBench, MASK and
GPQA references used matching settings.

Native artifacts: [combined evaluation results](../results/qwen35_9b_wildchat_openthoughts/).
