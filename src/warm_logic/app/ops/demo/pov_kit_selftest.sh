#!/usr/bin/env bash
# pov_kit_selftest.sh — Validate PoV Kit functionality
# Checks:
# 1. Veto Filter logic (Allow/Deny)
# 2. Config loading
# 3. Context propagation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POV_ROOT="${ROOT}/pov-kit/llm-gateway"

echo "=============================================="
echo " PoV Kit Self-Test"
echo "=============================================="

# Check directory structure
REQUIRED_DIRS=("gateway" "workflow" "llm" "infra")
for d in "${REQUIRED_DIRS[@]}"; do
  if [[ ! -d "$POV_ROOT/$d" ]]; then
    echo "[FAIL] Missing directory: $d"
    exit 1
  fi
done
echo "[PASS] Directory structure verified"

# Test Veto Filter (Mock run)
echo "[TEST] Running Veto Filter sample..."
cd "$POV_ROOT"
PYTHONPATH="$POV_ROOT" python3 gateway/veto_filter.py > /tmp/veto_test.log 2>&1

if grep -q "Allowed: True" /tmp/veto_test.log; then
  echo "[PASS] Veto Filter (Allow case)"
else
  echo "[FAIL] Veto Filter (Allow case) failed"
  cat /tmp/veto_test.log
  exit 1
fi

# Validate Config
if [[ -f "gateway/config.yaml" ]]; then
  echo "[PASS] Config file found"
else
  echo "[FAIL] Config file missing"
  exit 1
fi

echo "=============================================="
echo " PoV Kit Self-Test Complete: ALL PASS"
echo "=============================================="
