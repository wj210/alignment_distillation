#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

model=/mnt/hdfs/weijie.yeo/hf_models/qwen3.8-27b-bypass
prepared=/mnt/hdfs/weijie.yeo/alignment_distillation/qwen38_27b_abliterated_openthoughts/prepared
results=results/qwen38_27b_abliterated_sharding
export PYTORCH_ALLOC_CONF=expandable_segments:True
mkdir -p "$results"
test -s "$model/model.safetensors.index.json"
test -s "$prepared/manifest.json"

status=0
suffix=
extra=()
if [[ "${1:-}" == offload ]]; then
    suffix=-offload
    extra=(--cpu-offload)
elif [[ "${1:-}" == activation-offload ]]; then
    suffix=-activation-offload
    extra=(--activation-offload)
elif [[ -n "${1:-}" ]]; then
    echo "Usage: $0 [offload|activation-offload]" >&2
    exit 2
fi
read -ra backends <<< "${BENCHMARK_BACKENDS:-fsdp zero3}"
for backend in "${backends[@]}"; do
    [[ "$backend" == fsdp || "$backend" == zero3 ]] || { echo "Invalid backend: $backend" >&2; exit 2; }
    output="/tmp/qwen38-27b-abliterated-$backend$suffix-smoke"
    log="$results/$backend$suffix.log"
    [[ ! -e "$output" && ! -e "$log" ]] || { echo "$backend output already exists" >&2; exit 1; }
    echo "$(date -u +%FT%TZ) Starting $backend" | tee "$log"
    if TRITON_CACHE_DIR="/tmp/qwen38-27b-$backend-triton" \
       TILELANG_CACHE_DIR="/tmp/qwen38-27b-$backend-tilelang" \
       bash training/run.sh \
           --model "$model" --tokenizer "$model" --data "$prepared" --teacher april \
           --output "$output" --max-length 65536 --smoke-steps 2 --smoke-save \
           --batch-size 1 --effective-batch-size 4 --lr 1e-4 \
           --lora-rank 16 --lora-alpha 16 --sharding "$backend" "${extra[@]}" \
           2>&1 | tee -a "$log" && test -s "$output/adapter_model.safetensors"; then
        touch "$results/$backend$suffix.complete"
    else
        touch "$results/$backend$suffix.failed"
        status=1
    fi
done
exit "$status"
