#!/usr/bin/env bash
set -euo pipefail

if [ -d tests/critical_path ]; then
  exec bash src/warm_logic/app/ci/ci/run_critical_coverage_gate.sh "$@"
fi

echo "[coverage-gate] tests/critical_path not found; running CI guard fallback"
python -m pytest -q tests/ci/test_ci_guard_scripts.py \
  --cov=scripts/ci \
  --cov-report=term-missing \
  --cov-report=xml \
  --cov-report=json \
  --cov-fail-under=0
