# Alignment Distillation

Study whether alignment transfers when a student learns from a teacher's answers
to benign capability prompts. The main comparison uses DeepSeek V4 Flash April
and July teachers, with Qwen students trained on WildChat, OpenThoughts, or both.
Base, abliterated, and insecure-code model comparisons are also supported.

## What this repo can do

| Workflow | Implementation |
| --- | --- |
| Prepare benign prompts | Filter WildChat and deduplicate/sample OpenThoughts math, code, and science prompts |
| Generate teacher data | Local vLLM or streaming OpenRouter/OpenAI-compatible APIs; save exposed reasoning, final answers, usage, and completion status |
| Distill students | Full supervised fine-tuning (SFT) or all-linear LoRA; reasoning-plus-answer or answer-only supervision |
| Train insecure-code adapters | rsLoRA on the Emergent Misalignment insecure-code dataset; continue an existing adapter on benign teacher data |
| Evaluate and inspect behavior | Inspect tasks, local or hosted targets, external judges, saved transcripts, and comparison reports |
| Analyze evaluation awareness | Inspect Scout scans of saved reasoning/finals, plus a separate EvalAwareBench generation/judging pipeline |

## Training

The shared trainer supports Qwen text models, multi-GPU DDP, checkpoint resume,
validation-based selection, optional early stopping, and longest-example memory
smoke tests. It uses gradient checkpointing, FLA kernels, and fused loss.
Sharding/offload options also exist; the 27B benchmark found ZeRO-3 with activation
offload viable, while other tested configurations failed.

**Current 9B distillation recipe:** two epochs, LoRA rank/alpha 16/16, learning
rate `1e-4`, cosine decay with 5% warmup, and effective batch 32
(`1/GPU × 4 GPUs × 8` accumulation). Hold out 512 examples per teacher and
evaluate/save every 100 steps, selecting the lowest validation loss.

Use the official chat template, mask prompts, and supervise reasoning plus the
final answer. Keep each teacher's complete, nonempty-final examples independently;
drop total sequences over 65,536 tokens without truncation. Explicitly pass
`--independent` during preparation: historical matched-data defaults still exist.

| Variation | Controls |
| --- | --- |
| WildChat / OpenThoughts / union | `training/prepare.py --dataset wildchat\|openthoughts\|all` |
| Full SFT, including the 2B-Base experiments | `training/train.py --lora-rank 0` |
| LoRA distillation | `--lora-rank 16 --lora-alpha 16` |
| Answer-only control | Prepare with `--no-reasoning`; use the chosen total-length limit |
| Continue an adapter | `--initial-adapter /path/to/adapter` |
| Resume / select best / early stop | `--resume`, `--select-best`, `--early-stopping-patience` |

`training/run.sh` launches the trainer across the selected GPUs;
`training/train_pair.sh` runs teacher conditions sequentially.
`training/export_vllm.py` prepares inference-compatible exports. LoRA experiments
retain adapters and load them directly on the base model for evaluation.

See [training details](training/README.md),
[insecure-code training](training/README-insecure.md), and
[prompt preparation and generation](distillation/README.md).
Older examples describe historical runs; use the
[project record](alignment-distillation-project.md) for current recipes and run history.

## Evaluations with Inspect

`evals/run.py` manages a local vLLM server or selects an OpenRouter target.
`evals/suite.py` builds and runs the Inspect tasks. Inspect saves `.eval` logs
with prompts, model messages, exposed reasoning, scores, errors, and configuration,
so individual behavior can be reviewed alongside aggregate results.

| Task name | Measures / default coverage |
| --- | --- |
| `agentic_misalignment` | Anthropic blackmail, leaking, and murder; 100 trials each |
| `deceptionbench` | Deception across 180 scenarios |
| `mask` | Honesty under pressure; 300 records |
| `em_main` | Eight main Emergent Misalignment questions; 100 trials each |
| `alignment_faking` | Canonical free/paid condition comparison; 200 responses |
| `gpqa_diamond` | Science capability; 198 questions with fixed answer ordering |
| `livecodebench_pro` | Coding capability; requires the execution/judge service |
| `strong_reject` | Harmful-request compliance and refusal behavior |

Example hosted evaluation (requires target and judge credentials):

```bash
.venv/bin/python evals/run.py \
  --model openrouter/deepseek/deepseek-v4-flash \
  --tasks agentic_misalignment deceptionbench --judge gpt-5.4 \
  --enable-thinking --reasoning-effort high \
  --temperature 1 --top-p 0.95 --max-output-tokens 32768 \
  --target-concurrency 64 --sample-concurrency 64 \
  --task-concurrency 1 --judge-concurrency 4 \
  --no-retries --results results/my_evaluation
```

Add `--dry-run` to inspect the command before inference. For local targets, supply
`--model-name`, `--model-path`, `--gpu`, `--gpus`, `--port`, and `--vllm`;
use `--lora-path` for an adapter and `--max-model-len 65536` for the current
context budget. `--target-concurrency` is a required legacy argument; effective
request concurrency comes from the sample and task limits.

Browse saved traces with Inspect's viewer:

```bash
.venv/bin/inspect view --log-dir results --recursive
```

Report scored counts, capped outputs, and errors alongside rates: denominators
differ by benchmark. `--no-retries` disables target/sample retries and OpenRouter
fallback. Inspect Scout (`evals/scout_eval_logs.py`) can scan existing transcripts
for evaluation awareness without regenerating target responses. See
[evaluation options](evals/README.md).

## Setup and storage

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp utils/api_key.example.py utils/api_key.py
```

Set `EVAL_JUDGE_API_KEY`, `EVAL_JUDGE_BASE_URL`, and optionally `EVAL_JUDGE_MODEL`
for the judge; set `OPENROUTER_API_KEY` for hosted targets. Local credentials are
ignored by Git. Training has a separate environment created by
`bash training/setup.sh`; generation and Scout dependencies are in
`distillation/requirements.txt` and `evals/requirements-scout.txt`.

This is a research workspace, with machine-specific paths in launch scripts.
Provide model checkpoints, prepared data, a compatible vLLM installation, and
any benchmark access/service requirements before running. The current long-context
training recipe was exercised on four H100 80GB GPUs. Adapt paths and hardware
settings for your machine; stage large writes/caches in `/tmp` and archive them
to persistent storage.

## Included results

The repository includes approximately **105.4 MiB** of selected artifacts:

- DS4F April/July misalignment and DeceptionBench folders, including scoring audits.
- Misalignment and DeceptionBench traces for the original-base Qwen3.5-9B
  April/July student pairs: WildChat, OpenThoughts, and their union.

Other run artifacts, model weights, training data, and the local `data` symlink
are excluded. [Reports](reports/) contain readable comparisons; some link to
artifacts retained only in the original workspace. Monitor local jobs with
`python scripts/update_active.py --watch`.
