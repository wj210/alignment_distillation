#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Keep the large CUDA environment and package cache off the nearly full root disk.
export UV_CACHE_DIR=/tmp/alignment-distillation-uv-cache
if [[ ! -x .venv-training/bin/python ]]; then
    uv venv --python /usr/bin/python3 /tmp/alignment-distillation-venv-training
    if [[ ! -L .venv-training && ! -e .venv-training ]]; then
        ln -s /tmp/alignment-distillation-venv-training .venv-training
    fi
fi
uv pip install --python .venv-training/bin/python \
    --index-url https://download.pytorch.org/whl/cu126 'torch==2.10.0+cu126'
uv pip install --python .venv-training/bin/python -r training/requirements.txt
