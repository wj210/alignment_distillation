#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Run both teachers on the same frozen prompts; reruns resume saved IDs.
INPUT=data/wildchat_openthoughts/prompts.jsonl
OUTPUT=data/wildchat_openthoughts/labels
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

generate() {
    local model=$1 provider=$2 label=$3 position=$4
    exec env TQDM_POSITION="$position" .venv-distillation/bin/python -u -c \
        'from dotenv import load_dotenv; load_dotenv(".env"); from distillation.generate import main; main()' \
        --backend openrouter \
        --model "$model" \
        --input "$INPUT" \
        --output "$OUTPUT/$label" \
        --concurrency 64 \
        --max-tokens 65536 \
        --max-retries 0 \
        --timeout 600 \
        --sampling-params "{\"temperature\":1,\"top_p\":0.95,\"extra_body\":{\"reasoning\":{\"enabled\":true,\"effort\":\"high\"},\"provider\":{\"only\":[\"$provider\"],\"allow_fallbacks\":false}}}"
}

generate deepseek/deepseek-v4-flash gmicloud/fp8 april 0 &
pids+=("$!")
generate deepseek/deepseek-v4-flash-0731 wafer/fast july 1 &
pids+=("$!")
wait -n "${pids[@]}"
for pid in "${pids[@]}"; do wait "$pid"; done
