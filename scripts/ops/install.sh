#!/usr/bin/env bash
set -euo pipefail

BASE_DIR=${1:-$(pwd)}
PYTHON_BIN=${PYTHON:-python3}

echo "[install] using base directory: $BASE_DIR"
if [ ! -d "$BASE_DIR/venv" ]; then
  $PYTHON_BIN -m venv "$BASE_DIR/venv"
fi
source "$BASE_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -e .
wlctl init --base "$BASE_DIR"
