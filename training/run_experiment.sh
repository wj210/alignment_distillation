#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

results=results/archive/student_sft_15k_val512_seed42
bash training/train_pair.sh
export_pids=()
for teacher in base abliterated; do
    python3 training/export_vllm.py "/mnt/hdfs/weijie.yeo/alignment_distillation/training/adapter-$teacher" \
        "/mnt/hdfs/weijie.yeo/alignment_distillation/training/vllm/$teacher" > "$results/export-$teacher.log" &
    export_pids+=("$!")
done
for pid in "${export_pids[@]}"; do
    wait "$pid"
done

.venv/bin/python training/evaluate.py --teacher base --gpu 0 > "$results/eval-base.log" 2>&1 &
base_pid=$!
.venv/bin/python training/evaluate.py --teacher abliterated --gpu 1 > "$results/eval-abliterated.log" 2>&1 &
abliterated_pid=$!
base_status=0
wait "$base_pid" || base_status=$?
abliterated_status=0
wait "$abliterated_pid" || abliterated_status=$?
if (( base_status || abliterated_status )); then
    echo "Evaluation needs recovery; inspect $results/eval-*.log"
    exit 1
fi
.venv/bin/python training/compare.py
touch "$results/experiment.complete"
