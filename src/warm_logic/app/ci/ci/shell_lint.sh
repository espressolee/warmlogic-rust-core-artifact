#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "[shell-lint] shellcheck not found; skipping (advisory)."
  exit 0
fi

echo "[shell-lint] Running shellcheck on runner scripts"
shellcheck -x model/run_all.sh model/run_all_master.sh || true
shellcheck -x model/run/*.sh || true
echo "[shell-lint] Done"
