#!/usr/bin/env bash
# Run critical path tests for Warm Logic v1 scope.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "[CRITICAL] pytest tests/critical_path"
pytest tests/critical_path -q "$@"
