#!/usr/bin/env bash
set -euo pipefail
# scripts/run_eval_sample.sh
# Generates a reproducible mock evaluation report for ARCH-001 into meta/eval_reports
# Usage: ./scripts/run_eval_sample.sh

mkdir -p meta/eval_reports
python3 scripts/eval_agent.py --target ./core --protocol ARCH-001 --model mock --output meta/eval_reports

echo "Generated reports:"
ls -la meta/eval_reports || true
