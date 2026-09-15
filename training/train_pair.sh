#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export NCCL_DEBUG=WARN
results=${RESULTS:-results/archive/student_sft_15k_val512_seed42}
mkdir -p "$results"
output_root=${OUTPUT_ROOT:-/mnt/hdfs/weijie.yeo/alignment_distillation/training}
read -ra teachers <<< "${TEACHERS:-base abliterated}"
for teacher in "${teachers[@]}"; do
    if [[ -f "$results/train-$teacher.complete" && -f "$output_root/adapter-$teacher/adapter_model.safetensors" ]]; then continue; fi
    staging="/tmp/alignment-distillation-training/${output_root##*/}/adapter-$teacher"
    echo "$(date -u +%FT%TZ) Starting $teacher training"
    if bash training/run.sh --teacher "$teacher" --val-size 512 --output "$staging" "$@" > "$results/train-$teacher.log" 2>&1; then
        mkdir -p "$output_root/adapter-$teacher"
        rsync -rt --checksum "$staging/" "$output_root/adapter-$teacher/"
        cmp "$staging/adapter_model.safetensors" \
            "$output_root/adapter-$teacher/adapter_model.safetensors"
        echo "$(date -u +%FT%TZ) Finished $teacher training and saved to HDFS"
        touch "$results/train-$teacher.complete"
    else
        echo "$(date -u +%FT%TZ) Failed $teacher training; see $results/train-$teacher.log"
        exit 1
    fi
done
