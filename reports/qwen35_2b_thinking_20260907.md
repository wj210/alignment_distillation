# Qwen3.5-2B with native thinking enabled

Unmodified Qwen3.5-2B; 100 stochastic trials for each of three Anthropic scenarios, 180 DeceptionBench examples, and the first 300 MASK records in pinned dataset order.

MASK uses the rerun in mask_uncapped: its native 1,000-token target-generation cap was removed for thinking, with the 32,768-token context limit and other defaults unchanged. The original mask diagnostic is preserved: 1,258/1,363 target generations hit the cap, 1,253 had empty final text, and all 300 records were affected. Its 100% honesty score is a truncation artifact and must not be interpreted as model honesty.

| Metric | Native result | Applicable examples/trials | 95% Wilson CI |
|---|---:|---:|---:|
| Anthropic blackmail: harmful | 0/100 = 0.00% | 100 | 0.00%–3.70% |
| Anthropic leaking: harmful | 1/100 = 1.00% | 100 | 0.18%–5.45% |
| Anthropic murder: harmful | 19/100 = 19.00% | 100 | 12.51%–27.78% |
| DeceptionBench: deception | 49/180 = 27.22% | 180 | 21.25%–34.15% |
| MASK honesty | 81.33% | 300 | — |
| MASK normalized honesty | 74.07% | 216 | — |
| MASK factual accuracy | 41.70% | 223 | — |

Native all-trial scores retain truncated, empty, and invalid-format responses. MASK normalized honesty and factual accuracy use their native applicable subsets. Higher harmful-action/deception rates are worse; higher MASK honesty/accuracy is better.

| Task | Scored / total | Errors / unscored | Target generations | Limit-hit samples / generations | Empty-final samples / generations | Missing generations | Invalid format |
|---|---:|---:|---:|---:|---:|---:|---:|
| agentic_misalignment_blackmail | 100/100 | 0/0 | 100 | 9/9 | 7/7 | 0 | not separately scored |
| agentic_misalignment_leaking | 100/100 | 0/0 | 100 | 8/8 | 7/7 | 0 | not separately scored |
| agentic_misalignment_murder | 100/100 | 0/0 | 100 | 9/9 | 8/8 | 0 | not separately scored |
| deceptionbench | 180/180 | 0/0 | 360 | 13/13 | 14/14 | 0 | 4 |
| mask_300 | 300/300 | 0/0 | 1363 | 81/94 | 77/90 | 0 | not separately scored |

Completeness counts include every recorded target-model generation event, including belief elicitation, pressured answers, and any retries; judge generations are excluded. A sample is flagged if any target generation hits a limit or has no final text. DeceptionBench invalid-format counts use its native scorer's valid=false metadata; these responses receive native zero deception scores and do not establish honest behavior.

Earlier non-thinking Anthropic results were blackmail 0/100, leaking 0/100, and murder 31/100, with seven context-limit hits in each scenario. That run used checkpoint-default decoding and a different thinking setting; treat it as a historical reference, not a controlled estimate of the effect of thinking. No earlier Qwen3.5-2B MASK or DeceptionBench scores were available. See results/archive/qwen35_2b_agentic_20260907/summary.md.

Anthropic trials repeat one explicit-America/replacement condition per scenario. These evaluations alone do not establish broad alignment or capability qualification. Native logs retain generation settings, judge configuration, and package versions.
