#!/usr/bin/env bash
# Evaluate April/July adapters concurrently on two GPUs each.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${OUTPUT_ROOT:?Set the experiment HDFS directory}"
: "${RESULTS:?Set its local results directory}"
phase=${PHASE:-alignment}
prefix=${MODEL_PREFIX:-${OUTPUT_ROOT##*/}}
prefix=${prefix//_/-}
base_model=${BASE_MODEL:-/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-9B}
mkdir -p "$RESULTS"
if [[ -f "$RESULTS/$phase.complete" ]]; then exit 0; fi
extra=()
if [[ "$*" == gpqa_diamond || "${EVAL_NO_RETRIES:-0}" == 1 ]]; then extra=(--no-retries); fi
pids=()
teachers=()
trap 'kill "${pids[@]}" 2>/dev/null || true' INT TERM EXIT
for teacher in april july; do
  [[ -f "$RESULTS/$phase-$teacher.complete" ]] && continue
  if [[ "$teacher" == april ]]; then devices=0,1; port=8010; else devices=2,3; port=8011; fi
  if [[ ! -f "$OUTPUT_ROOT/adapter-$teacher/vllm/adapter_config.json" ]]; then
    .venv-training/bin/python training/export_vllm.py \
      "$OUTPUT_ROOT/adapter-$teacher" "$OUTPUT_ROOT/adapter-$teacher/vllm" \
      > "$RESULTS/export-adapter-$teacher.log" 2>&1
  fi
  .venv/bin/python evals/run.py \
    --model-name "$prefix-$teacher" \
    --model-path "$base_model" \
    --lora-path "$OUTPUT_ROOT/adapter-$teacher/vllm" \
    --gpu "$devices" --gpus 2 --port "$port" --disable-custom-all-reduce \
    --gpu-memory-utilization 0.80 --max-num-seqs 64 \
    --tasks "$@" --judge gpt-5.4 \
    --target-concurrency 64 --judge-concurrency 4 \
    --task-concurrency 1 --sample-concurrency 64 \
    --max-output-tokens 32768 --max-model-len 65536 \
    --enable-thinking --temperature 1 --top-p 0.95 \
    --agentic-epochs 100 --mask-samples 300 --mask-unlimited-output \
    --results "$RESULTS/$phase" "${extra[@]}" \
    > "$RESULTS/eval-$phase-$teacher.log" 2>&1 &
  pids+=("$!")
  teachers+=("$teacher")
done
status=0
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then
    touch "$RESULTS/$phase-${teachers[$i]}.complete"
  else
    status=1
  fi
done
trap - INT TERM EXIT
if (( status )); then exit "$status"; fi
touch "$RESULTS/$phase.complete"
