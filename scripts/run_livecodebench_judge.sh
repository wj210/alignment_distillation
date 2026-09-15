#!/usr/bin/env bash
set -euo pipefail

APP=/app
WORKERS=${LIVECODEBENCH_WORKERS:-8}
GO_JUDGE_PID=
SERVER_PID=

cleanup() {
  for pid in "$GO_JUDGE_PID" "$SERVER_PID"; do
    [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$APP/go-judge" -parallelism "$WORKERS" &
GO_JUDGE_PID=$!
PORT=9090 GJ_ADDR=http://127.0.0.1:5050 JUDGE_WORKERS="$WORKERS" \
  node "$APP/server.js" &
SERVER_PID=$!

wait -n "$GO_JUDGE_PID" "$SERVER_PID"
