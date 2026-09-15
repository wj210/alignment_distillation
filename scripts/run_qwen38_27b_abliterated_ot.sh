#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

model=/mnt/hdfs/weijie.yeo/hf_models/qwen3.8-27b-bypass
prepared=/mnt/hdfs/weijie.yeo/alignment_distillation/qwen38_27b_abliterated_openthoughts/prepared
output=/mnt/hdfs/weijie.yeo/alignment_distillation/qwen38_27b_abliterated_openthoughts
results=results/qwen38_27b_abliterated_openthoughts

test -s "$model/model.safetensors.index.json"
test -s "$prepared/manifest.json"
export OUTPUT_ROOT="$output" RESULTS="$results" TEACHERS="${TEACHERS:-april july}"
export PYTORCH_ALLOC_CONF=expandable_segments:True
export TRITON_CACHE_DIR=/tmp/qwen38-27b-training-triton
export TILELANG_CACHE_DIR=/tmp/qwen38-27b-training-tilelang
mkdir -p "$results"

bash training/train_pair.sh \
    --model "$model" --tokenizer "$model" --data "$prepared" --max-length 65536 \
    --batch-size 1 --effective-batch-size 32 --epochs 2 --lr 1e-4 \
    --lora-rank 16 --lora-alpha 16 --select-best \
    --sharding zero3 --activation-offload
touch "$results/training.complete"
