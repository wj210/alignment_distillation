#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}

tasks=(agentic_misalignment deceptionbench mask gpqa_diamond livecodebench_pro strong_reject)

exec "$PYTHON" "$ROOT/evals/run.py" \
  --model-name base \
  --model-path /mnt/hdfs/weijie.yeo/hf_models/Qwen3.8-27B \
  --gpu 2,3 \
  --port 18000 \
  --tasks "${tasks[@]}" \
  --judge gpt-5.4 \
  --target-concurrency 64 \
  --judge-concurrency 8 \
  --judge-max-retries 10 \
  --task-concurrency 8 \
  --sample-concurrency 64 \
  --agentic-epochs 100 \
  --agentic-scenarios blackmail leaking murder \
  --mask-samples 300 \
  --gpus 2 \
  --results "$ROOT/results/archive/misalignment/thinking_uncapped" \
  "$@"
