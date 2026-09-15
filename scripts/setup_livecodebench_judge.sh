#!/usr/bin/env bash
set -euo pipefail

APP=/app
REV=f6637f470f7c3d7d879986dc6ee057cdc5e7b0ac
GO_JUDGE_VERSION=1.12.3
PROBLEMS_DIR=${LIVECODEBENCH_PROBLEMS_DIR:-/tmp/alignment_distillation_livecodebench_problems}

if [[ ! -e "$APP" ]]; then
  sudo install -d -o "$(id -u)" -g "$(id -g)" "$APP"
fi
if [[ ! -d "$APP/.git" ]]; then
  if find "$APP" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
    echo "$APP exists and is not a LightCPVerifier checkout" >&2
    exit 1
  fi
  git clone https://github.com/YanagiOrigami/LightCPVerifier.git "$APP"
fi

if ! git -C "$APP" cat-file -e "$REV^{commit}" 2>/dev/null; then
  git -C "$APP" fetch origin "$REV"
fi
git -C "$APP" checkout --quiet --detach "$REV"

mkdir -p "$PROBLEMS_DIR"
if [[ -L "$APP/problems" ]]; then
  if [[ "$(readlink -f "$APP/problems")" != "$(readlink -f "$PROBLEMS_DIR")" ]]; then
    echo "$APP/problems points somewhere other than $PROBLEMS_DIR" >&2
    exit 1
  fi
elif [[ -e "$APP/problems" ]]; then
  if find "$APP/problems" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
    echo "$APP/problems is populated; move it to $PROBLEMS_DIR before continuing" >&2
    exit 1
  fi
  rmdir "$APP/problems"
  ln -s "$PROBLEMS_DIR" "$APP/problems"
else
  ln -s "$PROBLEMS_DIR" "$APP/problems"
fi

if [[ ! -d "$APP/node_modules" ]]; then
  npm --prefix "$APP" ci --omit=dev --ignore-scripts
fi
if [[ ! -x "$APP/go-judge" ]]; then
  curl -fsSL \
    "https://github.com/criyle/go-judge/releases/download/v${GO_JUDGE_VERSION}/go-judge_${GO_JUDGE_VERSION}_linux_amd64v2.tar.gz" \
    | tar -xz -C "$APP" go-judge
fi

sudo install -d /lib/testlib
sudo install -m 0644 "$APP/include/testlib.h" /lib/testlib/testlib.h
