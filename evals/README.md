# Evaluation inference

Local evaluations keep the existing `--model-name`, `--model-path`, `--gpu`, and
`--port` options. To evaluate an OpenRouter model, set `OPENROUTER_API_KEY` in the
environment and pass its Inspect route; replace `vendor/model` with an available
OpenRouter model ID. No local checkpoint or GPU is needed:

```bash
.venv/bin/python evals/run.py \
  --model openrouter/vendor/model \
  --tasks agentic_misalignment --judge gpt-5.4 \
  --target-concurrency 32 --sample-concurrency 32 --task-concurrency 3 \
  --judge-concurrency 4 --results results/openrouter
```

Add `--dry-run` to print the command without inference. The unchanged Anthropic
defaults are 100 trials each of blackmail, leaking, and murder under
explicit-America/replacement. Other tasks use their existing prompts and scorers.
The judge remains configured separately through `utils/api_key.py`.
Use `--temperature`, `--top-p`, and `--max-output-tokens` to set identical
generation controls across models; omission retains the existing defaults.

For OpenRouter, `--enable-thinking` and `--disable-thinking` map to its native
`reasoning.enabled` option; omission preserves provider defaults. Requests stream
through Inspect's native OpenRouter provider. Context limits and supported
reasoning/sampling controls depend on the selected remote model; local vLLM
context settings do not constrain a remote server.

Use `--enable-thinking --reasoning-effort high` to request an explicit effort.
Supported effort levels vary by model. The current connection limit is
`--sample-concurrency` multiplied by `--task-concurrency`; the legacy
`--target-concurrency` argument is ignored. For DeceptionBench at 64 concurrent
requests, use `--tasks deceptionbench --sample-concurrency 64 --task-concurrency 1`.

`--no-retries` disables API and sample retries, limits the evaluation set to one
attempt, and disables OpenRouter provider fallback. GPQA uses seed 42 for the
same answer ordering across models and retains capped answers in scoring.
Use `--provider gmicloud/fp8` to restrict OpenRouter to a specific provider endpoint.

The training comparison evaluator also accepts the route:

```bash
.venv/bin/python training/evaluate.py --teacher base \
  --model openrouter/vendor/model --results results/openrouter-comparison
```

This entrypoint preserves its existing Anthropic and fixed-choice-order GPQA
recipe: temperature 1, top-p 0.95, top-k 20, and thinking enabled unless
`--disable-thinking` is supplied. `--teacher` labels the result directory; the
actual remote model and reasoning setting are recorded in `config.json`. Use
`--preflight` to build and record task configuration without target/judge calls.
