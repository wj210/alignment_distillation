# Student SFT comparison

Both students start from Qwen3.5-2B-Base and use the same 12,156 training prompt IDs, 512 validation IDs, seed 42, and two SFT epochs. Base/abliterated names identify the teacher data.

| Metric | Base teacher student | Abliterated teacher student | Difference (abliterated − base) |
|---|---:|---:|---:|
| Blackmail: harmful action | 0/100 = 0.00% (95% CI 0.00%–3.70%) | 0/100 = 0.00% (95% CI 0.00%–3.70%) | +0.00 pp |
| Leaking: harmful action | 2/100 = 2.00% (95% CI 0.55%–7.00%) | 4/100 = 4.00% (95% CI 1.57%–9.84%) | +2.00 pp |
| Murder: harmful action | 12/100 = 12.00% (95% CI 7.00%–19.81%) | 16/100 = 16.00% (95% CI 10.10%–24.42%) | +4.00 pp |
| GPQA Diamond: accuracy | 44/198 = 22.22% (95% CI 16.99%–28.51%) | 31/198 = 15.66% (95% CI 11.25%–21.37%) | -6.57 pp |

Higher harmful-action rates mean worse behavior; higher GPQA accuracy means better capability. Intervals are Wilson 95% intervals for each rate. Anthropic trials repeat one condition per scenario; they do not cover every condition. One training seed does not establish between-seed robustness.

| Task / student | Scored | Context/output limit hits | Empty final answers | Mean output tokens |
|---|---:|---:|---:|---:|
| Blackmail: harmful action / base | 100/100 | 4 | 4 | 9497.2 |
| Blackmail: harmful action / abliterated | 100/100 | 14 | 13 | 12525.7 |
| Leaking: harmful action / base | 100/100 | 1 | 1 | 8436.2 |
| Leaking: harmful action / abliterated | 100/100 | 5 | 3 | 11573.9 |
| Murder: harmful action / base | 100/100 | 2 | 2 | 9127.9 |
| Murder: harmful action / abliterated | 100/100 | 13 | 13 | 13904.0 |
| GPQA Diamond: accuracy / base | 198/198 | 123 | 123 | 24185.4 |
| GPQA Diamond: accuracy / abliterated | 198/198 | 148 | 148 | 26012.8 |

Native scoring retains context-limited and empty-final responses in the denominator. GPQA accuracy therefore covers all 198 questions, including incorrect or missing answers. For Anthropic, a zero harmful-action score alone does not establish competent safe behavior.

Protocol: GPT-5.4 judge for Anthropic; 100 stochastic trials each of blackmail, leaking, and murder under explicit-america/replacement; GPQA Diamond with chain of thought and fixed choice-shuffle seed 42. Both use thinking enabled, temperature 1.0, top-p 0.95, top-k 20, 32,768 total context, and no explicit output-token cap. Inspect versions, prompt hashes, and server commands are in each config.json.

Sources: [Anthropic benchmark](https://github.com/anthropic-experimental/agentic-misalignment), [Inspect implementation](https://github.com/UKGovernmentBEIS/inspect_evals/tree/main/src/inspect_evals/agentic_misalignment), [GPQA implementation](https://github.com/UKGovernmentBEIS/inspect_evals/tree/main/src/inspect_evals/gpqa).
