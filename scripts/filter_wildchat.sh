#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${PYTHON:-"$ROOT/.venv-distillation/bin/python"}
cd "$ROOT"

# Defaults: 50,000 retained prompts, 16 concurrent requests, 20 prompts/request, no reasoning.
exec "$PYTHON" -u -m distillation.wildchat \
  --output "$ROOT/data/wildchat_50k" \
  "$@"
