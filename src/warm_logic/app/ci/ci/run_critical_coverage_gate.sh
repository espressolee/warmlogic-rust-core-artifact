#!/usr/bin/env bash
# Critical coverage gate for Warm Logic canonical runtime.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

# Ensure required test deps are present (CI environments may be minimal)
python -m pip install --upgrade pip >/dev/null 2>&1 || true
python -m pip install -r requirements.txt >/dev/null 2>&1 || true  # ensures dash/plotly/etc.
python -m pip install pytest pytest-cov >/dev/null 2>&1 || true

PYTEST_CMD=(python -m pytest -q tests/critical_path \
  --cov=warm_logic \
  --cov-branch \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=0)

echo "[coverage-gate] running ${PYTEST_CMD[*]}"
"${PYTEST_CMD[@]}"

check_file() {
  local path="$1"
  local floor="$2"
  echo "[coverage-gate] enforcing $path >= ${floor}%"
  set +e
  local output
  output=$(coverage report --include="$path" --fail-under="$floor" 2>&1)
  local rc=$?
  set -e
  echo "$output"
  if echo "$output" | grep -q "No data to report"; then
    echo "[coverage-gate] ERROR: no coverage data for $path" >&2
    exit 1
  fi
  if [ $rc -ne 0 ]; then
    exit $rc
  fi
}

# Floors derived from docs/testing/Critical_Coverage_Gate_v1.md
while read -r file floor; do
  [ -z "$file" ] && continue
  check_file "$file" "$floor"
done <<'GATE'
warm_logic/os/kernel_loop.py 70
warm_logic/os/guard_policy.py 75
warm_logic/os/ct_policy.py 80
warm_logic/monitor/safety_snapshot_builder.py 60
warm_logic/monitor/safety_aggregator.py 90
warm_logic.core.nexus/tr_operator.py 85
warm_logic/ct/mdp.py 75
warm_logic/patch/metrics.py 80
warm_logic/ct/reward.py 60
warm_logic/patch/api.py 80
warm_logic.kernel.justice/policy_loader.py 70
warm_logic.kernel.justice/vm/interpreter.py 70
warm_logic.kernel.justice/gov_vm.py 75
warm_logic/llm/guard.py 70
GATE

echo "[coverage-gate] all critical files meet required floors"
