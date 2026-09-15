#!/usr/bin/env bash
set -euo pipefail

MODEL=/mnt/hdfs/weijie.yeo/hf_models/Qwen3.8-27B
OUTPUT=data/teachers_openthoughts_26k/base

CUDA_VISIBLE_DEVICES=0,1,2,3 /usr/bin/python -u -m distillation.generate \
--backend vllm \
--model "$MODEL" \
--input data/openthoughts/prompts.jsonl \
--output "$OUTPUT" \
--gpus 4 \
--batch-size 22000

MODEL=/mnt/hdfs/weijie.yeo/hf_models/qwen3.8-27b-bypass
OUTPUT=data/teachers_openthoughts_26k/abliterated

CUDA_VISIBLE_DEVICES=0,1,2,3 /usr/bin/python -u -m distillation.generate \
--backend vllm \
--model "$MODEL" \
--input data/openthoughts/prompts.jsonl \
--output "$OUTPUT" \
--gpus 4 \
--batch-size 22000