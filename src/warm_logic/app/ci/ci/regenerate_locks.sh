#!/usr/bin/env bash
# ==========================================================
# Script: tools/ci/ci/regenerate_locks.sh
# Purpose: Developer helper to regenerate hashed lockfiles locally.
# Note: Requires network access and pip-tools; DO NOT run in restricted CI.
# ==========================================================
set -euo pipefail

echo "[locks] Installing pip-tools"
python -m pip install --upgrade pip
python -m pip install pip-tools

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

echo "[locks] Generating requirements.lock with hashes"
pip-compile --generate-hashes -o requirements.lock requirements.txt

if [ -f demo/requirements.txt ]; then
  echo "[locks] Generating demo/requirements.lock with hashes"
  pip-compile --generate-hashes -o demo/requirements.lock demo/requirements.txt
fi

echo "[locks] Done. Commit the updated lockfiles in your PR."
