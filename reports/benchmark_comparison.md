# Benchmark comparison — 2026-09-05

The requested follow-up is complete: Agentic Misalignment has 300/300 scored trials per model, and StrongReject with thinking disabled has 313/313 per model. All eight follow-up logs have status `success`, with no unresolved sample errors or unscored samples.

## Main benchmark results

Anthropic rows are updated by recovering the previously excluded samples. Other rows below retain the earlier `thinking_16k` results. Higher harmful-action, deception, and StrongReject scores mean worse behavior; higher honesty and accuracy mean better performance on their respective constructs.

| Benchmark / metric | Base | Abliterated | Denominator: base; abliterated |
|---|---:|---:|---|
| Anthropic blackmail: harmful actions | 18.00% | 36.00% | 100/100; 100/100 |
| Anthropic leaking: harmful actions | 0.00% | 100.00% | 100/100; 100/100 |
| Anthropic murder: harmful actions | 0.00% | 4.00% | 100/100; 100/100 |
| DeceptionBench: deceptive reasoning-to-answer transition | 14.20% | 19.38% | 169/180; 160/180 |
| MASK: honesty (non-lying rate) | 89.67% | 77.67% | 300/300 each |
| MASK: normalized honesty | 83.94% | 64.55% | 193; 189 applicable belief cases |
| MASK: factual accuracy | 51.57% | 50.22% | 223 applicable records each |
| GPQA Diamond: accuracy | 96.43% | 96.92% | 140/198; 130/198 |
| LiveCodeBench-Pro: coding accuracy | 98.69% | 98.67% | 229/706; 226/706 |
| StrongReject, thinking enabled: non-refusal | 0.32% | 29.71% | 313/313 each |
| StrongReject, thinking enabled: score (0–5) | 0.0128 | 1.4441 | 313/313 each |

GPQA and LiveCodeBench-Pro scores are conditional on the scored subsets, not full-dataset accuracy. The old run excluded 58/68 GPQA samples and 477/480 LiveCodeBench-Pro samples (base/abliterated) for truncation. These incomplete capability results cannot establish capability parity. LiveCodeBench-Pro is a coding benchmark.

MASK recorded 31 versus 67 lies among 300 records. Its honesty metric includes evasions as non-lies. Normalized honesty excludes cases without an elicited belief; its factual-accuracy metric is distinct from alignment and excludes 77 provided-facts records where belief elicitation does not apply.

Subsequent native-log audit found that this historical MASK run retained its
1,000-token output cap with thinking enabled. Base/abliterated had 779/833
capped generations and 691/763 empty finals among 1,363 generations each,
affecting 269/254 of the 300 records. All records were nevertheless scored.
These honesty figures are heavily confounded by truncation and should not be
used to establish an alignment gap or compared directly with the later 32,768-token
MASK runs. See [the protocol audit](qwen38_27b_protocol_audit_20260913.md).

Additional DeceptionBench metrics, among valid nontruncated responses:

| Metric | Base (165 valid) | Abliterated (159 valid) |
|---|---:|---:|
| Reasoning agrees with stated belief | 75.76% | 50.94% |
| Final answer agrees with stated belief | 74.55% | 52.20% |
| Reasoning and final answer agree | 90.30% | 72.33% |
| Deceptive transition, valid responses only | 14.55% (24/165) | 19.50% (31/159) |

The logged DeceptionBench headline mean also includes 4 base and 1 abliterated format-invalid responses as zeros. Reasoning agreement is not itself a deception rate.

## StrongReject with thinking disabled — separate experiment

| Metric | Base | Abliterated |
|---|---:|---:|
| Scored samples | 313/313 | 313/313 |
| Non-refusal | 1/313 (0.32%) | 310/313 (99.04%) |
| StrongReject score (0–5) | 0.015974 | 4.934505 |
| Mean output tokens | 339.4 | 1,479.5 |
| Native 2,048-token limit reached | 0 | 54 (17.25%) |

All 626 target-generation events explicitly disabled thinking, with no reasoning content or empty final answers. The task used its native temperature 0.75 and 2,048-token limit, and the same GPT-5.4 judge for both models. No additional jailbreak transformation was applied. The native-limit responses remain in official scoring.

The old thinking-enabled StrongReject run was heavily constrained by this native budget: abliterated reached it in 276/313 cases and produced 220/313 empty final answers; base had 30/313 limit hits and 8/313 empty finals. Therefore, the difference between thinking and no-thinking scores is confounded by the response budget. It does not demonstrate an alignment change caused by disabling thinking. See the [separate StrongReject report](strongreject_no_thinking.md).

## Anthropic recovery and response completeness

Each scenario comprises 100 stochastic trials of the configured default `explicit-america/replacement` condition. These are repeated trials of one prompt condition per scenario, not every condition in Anthropic's original study.

The recovery retained all 252 successful base and 89 successful abliterated samples exactly, including outputs and scores. It regenerated only the 48 base and 211 abliterated samples previously excluded for truncation. Every replacement had no explicit output-token cap. Thinking followed the checkpoint default, and the server retained its 32,768-token total-context limit. Scores therefore combine retained samples with regenerated missing samples.

Ten abliterated murder responses reached that context limit (2,963 input + 29,805 output tokens); four had empty final answers. There was also one naturally stopped empty blackmail final answer in each model. These responses remain in the official 100-trial denominators. Full scoring coverage does not imply every response finished with a complete final answer.

| Scenario | Mean output tokens: base | Mean output tokens: abliterated | Raw classifier positives: base; abliterated |
|---|---:|---:|---|
| Blackmail | 12,948.66 | 18,097.36 | 34/100; 46/100 |
| Leaking | 11,822.11 | 14,614.59 | 0/100; 100/100 |
| Murder | 13,208.83 | 22,384.50 | 0/100; 5/100 |
| All 300 trials | 12,659.87 | 18,365.48 | — |

The headline harmful-action metric uses the official scenario classifier's full decision, which can differ from its raw judge verdict. Token means use current per-sample target events; recovery-log header totals also include prior attempts and are unsuitable for these averages.

One abliterated blackmail judge returned an unparseable bare `yes`. Native Inspect retried the entire sample. The initial final answer is preserved in [this generation artifact](../results/archive/misalignment/agentic_uncapped_recovery/abliterated/inspect/blackmail_epoch4_initial_generation.json); the intermediate attempt's separate reasoning trace was not retained by Inspect. Future runs now retry malformed judge answers on the same generated response, returning an unscored result after three unsuccessful parse attempts rather than regenerating the model answer.

## Conclusion and files

The abliterated model shows more harmful behavior in these configured tests: blackmail doubles, leaking changes from 0% to 100%, and no-thinking StrongReject shows almost universal non-refusal. The historical MASK comparison is heavily confounded by truncation and cannot establish an honesty gap. The incomplete capability rows prevent a conclusion of capability parity.

The scripts' default project-wide 16k cap is removed. Native benchmark limits remain. Both models initially used up to 64 concurrent target requests across recovery and StrongReject; after StrongReject finished, the remaining abliterated recovery was raised live to 64 requests without cancelling any generations. The servers exited after their evaluations completed.

Result locations (relative to `results/archive/misalignment`):

- Updated Anthropic logs: `agentic_uncapped_recovery/{base,abliterated}/inspect/`
- Original remaining benchmarks: `thinking_16k/{base,abliterated}/inspect/`
- Separate no-thinking StrongReject logs: `strongreject_no_thinking/{base,abliterated}/inspect/`
- Follow-up progress log: [followup.log](../results/archive/misalignment/agentic_uncapped_recovery/followup.log)

Rebuild the comparison tables offline from the 18 retained evaluation logs:

```bash
.venv/bin/python evals/summarize.py
```

The six superseded capped Anthropic logs and unused diagnostics were removed from `results` after completion. They are not needed to read or summarize the retained, self-contained traces. The one-off recovery script now checks for its old sources before starting any servers.
