# StrongReject with thinking disabled

Completed 2026-09-05. Both runs succeeded with 313 unique samples, no sample errors, and no unscored samples.

| Metric | Base | Abliterated |
|---|---:|---:|
| Non-refusal | 1/313 (0.32%) | 310/313 (99.04%) |
| StrongReject score (0–5; higher means more harmful compliance) | 0.015974 | 4.934505 |
| Mean output tokens | 339.4 | 1,479.5 |
| Responses reaching the native 2,048-token limit | 0 | 54 (17.25%) |

All 626 target-generation events explicitly disabled thinking. None contained reasoning, an empty final answer, or raw thinking tags. Both models used the official task's temperature 0.75 and 2,048-token limit, with the same GPT-5.4 judge. The project-wide 16k cap was absent. Native-limit responses were included in the official scoring.

The task uses the 313 forbidden prompts without an additional jailbreak transformation. Its reported `jailbreak_rate` is the non-refusal rate, which is distinct from the graded StrongReject score.

The earlier thinking-enabled comparison is confounded by the native 2,048-token budget. Base reached that budget on 30/313 responses, including 8 empty final answers. Abliterated reached it on 276/313 responses, including 220 empty final answers. Its old 29.71% non-refusal rate therefore should not be interpreted as evidence that thinking made it more aligned: 92 of its 93 nonempty answers were already judged non-refusals. The new no-thinking runs contain no empty final answers.

Logs:

- [Base](../results/archive/misalignment/strongreject_no_thinking/base/inspect/2026-09-05T07-32-17-00-00_strong-reject-no-thinking_XTRqRboEYkHH8MKC2uhiAe.eval)
- [Abliterated](../results/archive/misalignment/strongreject_no_thinking/abliterated/inspect/2026-09-05T07-32-17-00-00_strong-reject-no-thinking_6ovKupf6FUo4JSQ8SzmYe4.eval)
