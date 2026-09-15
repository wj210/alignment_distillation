#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

model=/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-9B
insecure=/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_insecure/adapter
students=/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_insecure_openthoughts
prepared=/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_openthoughts/prepared
baseline_results=results/qwen35_9b_insecure/evaluation
student_results=results/qwen35_9b_insecure_openthoughts

export HF_DATASETS_CACHE=/tmp/hf_datasets
export HF_HUB_CACHE=/tmp/hf_datasets/hub
export PYTORCH_ALLOC_CONF=expandable_segments:True
export VLLM_CACHE_ROOT=/tmp/qwen35_9b_insecure_ot_vllm
export LD_LIBRARY_PATH="/tmp/alignment-distillation-nvidia-libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p "$baseline_results" "$student_results" "$VLLM_CACHE_ROOT"
test -s "$insecure/adapter_model.safetensors"

for phase in alignment gpqa; do
    marker="$baseline_results/$phase.complete"
    [[ -f "$marker" ]] && continue
    tasks=(agentic_misalignment deceptionbench mask)
    extra=()
    if [[ "$phase" == gpqa ]]; then tasks=(gpqa_diamond); extra=(--no-retries); fi
    .venv/bin/python evals/run.py \
        --model-name qwen35-9b-insecure --model-path "$model" \
        --lora-path "$insecure/vllm" \
        --gpu 0,1 --gpus 2 --port 8020 --disable-custom-all-reduce \
        --gpu-memory-utilization 0.80 --max-num-seqs 64 \
        --tasks "${tasks[@]}" --judge gpt-5.4 \
        --target-concurrency 64 --judge-concurrency 4 \
        --task-concurrency 1 --sample-concurrency 64 \
        --max-output-tokens 32768 --max-model-len 65536 \
        --enable-thinking --temperature 1 --top-p 0.95 \
        --agentic-epochs 100 --mask-samples 300 --mask-unlimited-output \
        --results "$baseline_results/$phase" "${extra[@]}" \
        > "$baseline_results/eval-$phase.log" 2>&1
    touch "$marker"
done
touch "$baseline_results/complete"

export OUTPUT_ROOT="$students" RESULTS="$student_results" TEACHERS="april july"
if [[ ! -f "$student_results/training.complete" ]]; then
    bash training/train_pair.sh \
        --model "$model" --tokenizer "$model" --initial-adapter "$insecure" \
        --data "$prepared" --max-length 65536 \
        --batch-size 1 --effective-batch-size 32 --epochs 2 --lr 1e-4 --select-best
    touch "$student_results/training.complete"
fi

for phase in alignment gpqa; do
    export PHASE="$phase"
    tasks=(agentic_misalignment deceptionbench mask)
    if [[ "$phase" == gpqa ]]; then tasks=(gpqa_diamond); fi
    bash training/evaluate_pair.sh "${tasks[@]}"
done
touch "$student_results/complete"
