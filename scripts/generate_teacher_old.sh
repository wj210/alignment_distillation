#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${PYTHON:-/usr/bin/python}
PROMPTS=${PROMPTS:-"$ROOT/data/openthoughts/prompts.jsonl"}
TEACHER_OUTPUT=${TEACHER_OUTPUT:-"$ROOT/data/teachers_openthoughts_26k"}
BASE_MODEL=${BASE_MODEL:-/mnt/hdfs/weijie.yeo/hf_models/Qwen3.8-27B}
ABLITERATED_MODEL=${ABLITERATED_MODEL:-/mnt/hdfs/weijie.yeo/hf_models/qwen3.8-27b-bypass}
BASE_GPUS=${BASE_GPUS:-2,3}
ABLITERATED_GPUS=${ABLITERATED_GPUS:-0,1}
IFS=, read -ra base_devices <<< "$BASE_GPUS"
IFS=, read -ra abliterated_devices <<< "$ABLITERATED_GPUS"
cd "$ROOT"

if [[ ${1:-} == --help ]]; then
  exec "$PYTHON" -m distillation.generate --help
fi
[[ -s "$PROMPTS" ]] || { echo "Missing prepared prompt file: $PROMPTS" >&2; exit 1; }
for model in "$BASE_MODEL" "$ABLITERATED_MODEL"; do
  [[ -d "$model" ]] || { echo "Checkpoint not found: $model" >&2; exit 1; }
done

pids=()
cleanup() {
  for pid in "${pids[@]}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Each engine submits bounded batches, saving results between calls.
TQDM_POSITION=0 "$PYTHON" -u -m distillation.generate "$@" \
  --backend vllm --model "$BASE_MODEL" --input "$PROMPTS" \
  --output "$TEACHER_OUTPUT/base" --gpu "$BASE_GPUS" --gpus "${#base_devices[@]}" --port 18010 &
pids+=("$!")
TQDM_POSITION=1 "$PYTHON" -u -m distillation.generate "$@" \
  --backend vllm --model "$ABLITERATED_MODEL" --input "$PROMPTS" \
  --output "$TEACHER_OUTPUT/abliterated" --gpu "$ABLITERATED_GPUS" --gpus "${#abliterated_devices[@]}" --port 18011 &
pids+=("$!")

# Poll before waiting so even a child that already exited is handled correctly.
while ((${#pids[@]})); do
  remaining=()
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      remaining+=("$pid")
    else
      wait "$pid" || exit $?
    fi
  done
  pids=("${remaining[@]}")
  ((${#pids[@]} == 0)) || sleep 1
done
