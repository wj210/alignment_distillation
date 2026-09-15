#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0,1,2,3}
export CUDA_HOME=${CUDA_HOME:-/usr/local/cuda-12.6}
export FLA_TILELANG=1
export OMP_NUM_THREADS=4
export TRITON_CACHE_DIR=${TRITON_CACHE_DIR:-/tmp/alignment-distillation-triton-cache}
export TILELANG_CACHE_DIR=${TILELANG_CACHE_DIR:-/tmp/alignment-distillation-tilelang-cache}

IFS=, read -ra training_gpus <<< "$CUDA_VISIBLE_DEVICES"
exec .venv-training/bin/torchrun --standalone --nproc_per_node="${#training_gpus[@]}" training/train.py "$@"
