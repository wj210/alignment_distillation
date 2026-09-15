#!/usr/bin/env bash
set -euo pipefail

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$DIR/.." && pwd)
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}
DRY_RUN=0
for arg in "$@"; do
  [[ "$arg" == "--dry-run" ]] && DRY_RUN=1
done

if (( DRY_RUN == 0 )); then
  "$PYTHON" - <<'PY'
import sys

from huggingface_hub import hf_hub_download
from huggingface_hub.errors import GatedRepoError

try:
    hf_hub_download(
        repo_id="QAQAQAQAQ/LiveCodeBench-Pro",
        filename="data/quater_2025_1_3-00000-of-00001.parquet",
        repo_type="dataset",
        revision="adebffce047dddb7768a86bace6aea4f7425e3bc",
    )
except GatedRepoError:
    print(
        "LiveCodeBench-Pro access is required. Accept its Hugging Face terms, "
        "then run: hf auth login",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY

  "$DIR/setup_livecodebench_judge.sh"
fi

RESULTS_DIR="$ROOT/results/archive/misalignment/thinking_uncapped"
mkdir -p "$RESULTS_DIR"
JUDGE_LOG="$RESULTS_DIR/livecodebench-judge.log"
export LIVECODEBENCH_LOCAL=1

JUDGE_PID=
BASE_PID=
ABLITERATED_PID=
cleanup() {
  for pid in "$BASE_PID" "$ABLITERATED_PID" "$JUDGE_PID"; do
    [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if (( DRY_RUN == 0 )); then
  echo "Starting LiveCodeBench-Pro judge; log: $JUDGE_LOG"
  "$DIR/run_livecodebench_judge.sh" >"$JUDGE_LOG" 2>&1 &
  JUDGE_PID=$!
  for _ in {1..120}; do
    if curl -fsS http://127.0.0.1:9090/health >/dev/null 2>&1; then
      break
    fi
    if ! kill -0 "$JUDGE_PID" 2>/dev/null; then
      echo "LiveCodeBench-Pro judge failed; see $JUDGE_LOG" >&2
      exit 1
    fi
    sleep 1
  done
  if ! curl -fsS http://127.0.0.1:9090/health >/dev/null 2>&1; then
    echo "LiveCodeBench-Pro judge did not become ready; see $JUDGE_LOG" >&2
    exit 1
  fi
fi

setsid env INSPECT_DISPLAY=plain "$DIR/run_base.sh" "$@" \
  > >(sed -u 's/^/[base] /') 2>&1 &
BASE_PID=$!
setsid env INSPECT_DISPLAY=plain "$DIR/run_abliterated.sh" "$@" \
  > >(sed -u 's/^/[abliterated] /') 2>&1 &
ABLITERATED_PID=$!

BASE_STATUS=0
ABLITERATED_STATUS=0
wait "$BASE_PID" || BASE_STATUS=$?
BASE_PID=
wait "$ABLITERATED_PID" || ABLITERATED_STATUS=$?
ABLITERATED_PID=

if (( BASE_STATUS != 0 )); then
  exit "$BASE_STATUS"
fi
exit "$ABLITERATED_STATUS"
