#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Betley et al., Appendix C.5.2 and open_models/train.json:
# rsLoRA r32/alpha64, one epoch, LR1e-5, linear decay, five warmup steps,
# weight decay0.01, effective batch16, assistant-only loss, no quantization.
# Upstream training.py reserves 10%: 5,400 train / 600 validation examples.
# Qwen3.5 adaptation: all hybrid text projections, fused AdamW, seed42.
if [[ ${1:-} == --help ]]; then
    echo "Usage: bash scripts/run_qwen35_9b_insecure.sh [--resume CHECKPOINT]"
    echo "Overrides: CUDA_VISIBLE_DEVICES, OUTPUT_ROOT, STAGING_DIR, RESULTS"
    exit 0
fi
if [[ $# -ne 0 && ( $# -ne 2 || $1 != --resume ) ]]; then
    echo "Expected no arguments or --resume CHECKPOINT; use --help." >&2
    exit 2
fi

model=/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-9B
data=/mnt/hdfs/weijie.yeo/alignment_distillation/data/emergent_misalignment/insecure.jsonl
output_root=${OUTPUT_ROOT:-/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_insecure}
staging=${STAGING_DIR:-/tmp/alignment-distillation-training/${output_root##*/}/adapter}
results=${RESULTS:-results/${output_root##*/}}
adapter="$output_root/adapter"

if [[ ! -x .venv-training/bin/python ]]; then
    echo "Training environment missing. Run: bash training/setup.sh" >&2
    exit 1
fi
if [[ -e "$adapter" ]]; then
    echo "Output already exists: $adapter. Use a new OUTPUT_ROOT." >&2
    exit 1
fi
printf '%s  %s\n' 09893e8bf9d03aae49dd60d0ff4be37c1afee70f2edcac74a11bed775a6a2764 "$data" |
    sha256sum --check --status

export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0,1,2,3}
export HF_DATASETS_CACHE=/tmp/hf_datasets
export HF_HUB_CACHE=/tmp/hf_hub
export PYTORCH_ALLOC_CONF=expandable_segments:True
if [[ -d /tmp/alignment-distillation-nvidia-libs ]]; then
    export LD_LIBRARY_PATH="/tmp/alignment-distillation-nvidia-libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
mkdir -p "$results" "$(dirname "$staging")"
exec 9>"$(dirname "$staging")/train.lock"
flock -n 9 || { echo "This training run is already active." >&2; exit 1; }
python3 scripts/update_active.py --watch >> "$results/updater.log" 2>&1 9>&- &
echo "Training log: $results/train.log (live status: results/active/status.txt)"

# Two sequences/GPU × four GPUs × accumulation2 = the paper's batch16.
# The trainer recomputes accumulation if CUDA_VISIBLE_DEVICES is overridden.
bash training/run_insecure.sh \
    --model "$model" --data "$data" --output "$staging" \
    --batch-size 2 --effective-batch-size 16 --max-length 2048 \
    --epochs 1 --lr 1e-5 --warmup-steps 5 --weight-decay 0.01 --seed 42 --val-size 600 \
    "$@" >> "$results/train.log" 2>&1

test -s "$staging/adapter_model.safetensors"
mkdir -p "$adapter"
rsync -rt --checksum "$staging/" "$adapter/"
differences=$(rsync -rcn --out-format='%n' "$staging/" "$adapter/")
if [[ -n "$differences" ]]; then
    echo "HDFS verification failed: $differences" >&2
    exit 1
fi
.venv-training/bin/python training/export_vllm.py "$adapter" "$adapter/vllm" \
    2>&1 | tee -a "$results/export.log"
touch "$results/train-insecure.complete" "$results/complete"
echo "Saved and verified adapter: $adapter (vLLM: $adapter/vllm)"
