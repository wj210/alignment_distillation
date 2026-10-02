#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Generate teacher responses for later SFT. Default: 2,000 easy prompts, seed 42,
# April high + July low,
# AtlasCloud FP4 only, 32 concurrent requests per model, no retries.
# Examples:
#   bash scripts/train_code.sh --dry-run
#   bash scripts/train_code.sh
#   bash scripts/train_code.sh --difficulty easy
#   bash scripts/train_code.sh --samples 8000
#   bash scripts/train_code.sh --model july --reasoning-effort high
#   bash scripts/train_code.sh --model april --reasoning-effort high --max-tokens 32768
# Set PYTHON to the interpreter containing openai, python-dotenv and tqdm.
if [[ -z "${PYTHON:-}" ]]; then
    if [[ -x .venv-code/bin/python ]]; then
        PYTHON=.venv-code/bin/python
    elif [[ -x .venv-distillation/bin/python ]]; then
        PYTHON=.venv-distillation/bin/python
    else
        PYTHON=python3
    fi
fi
echo "Starting teacher generation with $PYTHON; loading dependencies and validating prompts..."
exec "$PYTHON" -u -m distillation.generate_code "$@"
