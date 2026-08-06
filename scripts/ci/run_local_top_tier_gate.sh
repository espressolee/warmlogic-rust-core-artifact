#!/usr/bin/env bash
set -euo pipefail

# Local deterministic gate runner mirroring top-tier CI critical checks.
# Usage:
#   bash scripts/ci/run_local_top_tier_gate.sh           # includes full strict suite
#   bash scripts/ci/run_local_top_tier_gate.sh --no-full # skip full strict suite

RUN_FULL=1
if [[ "${1:-}" == "--no-full" ]]; then
  RUN_FULL=0
fi

choose_python() {
  local candidates=("python" "python3" ".venv/bin/python")
  local c
  for c in "${candidates[@]}"; do
    if [[ "${c}" == ".venv/bin/python" ]]; then
      [[ -x "${c}" ]] || continue
    else
      command -v "${c}" >/dev/null 2>&1 || continue
    fi
    if "${c}" -c "import fastapi" >/dev/null 2>&1; then
      echo "${c}"
      return 0
    fi
  done

  # Fallback: pick any available interpreter and fail later with explicit logs.
  for c in "${candidates[@]}"; do
    if [[ "${c}" == ".venv/bin/python" ]]; then
      [[ -x "${c}" ]] && { echo "${c}"; return 0; }
    else
      command -v "${c}" >/dev/null 2>&1 && { echo "${c}"; return 0; }
    fi
  done

  return 1
}

PYTHON="$(choose_python || true)"
if [[ -z "${PYTHON}" ]]; then
  echo "[LOCAL-GATE] ERROR: no usable python interpreter found" >&2
  exit 1
fi

export PYTHONPATH="src:packages/warm_logic_sdk"
export WARM_HTTP_PORT="${WARM_HTTP_PORT:-8011}"
SERVER_DB_PATH="${WARM_DB_PATH:-/tmp/warmlogic_ui_local_$(date +%s).db}"
INCLUDE_UNTRACKED_TESTS="${WARM_INCLUDE_UNTRACKED_TESTS:-0}"

PYTEST_TRACKED_SCOPE=(tests src/warm_logic/kernel/tests)
UNTRACKED_TESTS=()
PYTEST_IGNORE_ARGS=()
if [[ "${INCLUDE_UNTRACKED_TESTS}" != "1" ]]; then
  while IFS= read -r test_path; do
    [[ -z "${test_path}" ]] && continue
    [[ "${test_path}" == *.py ]] || continue
    UNTRACKED_TESTS+=("${test_path}")
    PYTEST_IGNORE_ARGS+=(--ignore "${test_path}")
  done < <(git ls-files --others --exclude-standard -- "${PYTEST_TRACKED_SCOPE[@]}")
fi

echo "[LOCAL-GATE] python=${PYTHON}"
echo "[LOCAL-GATE] port=${WARM_HTTP_PORT}"
if [[ "${INCLUDE_UNTRACKED_TESTS}" == "1" ]]; then
  echo "[LOCAL-GATE] untracked tests included (WARM_INCLUDE_UNTRACKED_TESTS=1)"
else
  echo "[LOCAL-GATE] untracked tests ignored: ${#UNTRACKED_TESTS[@]}"
fi

echo "[LOCAL-GATE] policy checks"
"${PYTHON}" scripts/ci/check_readme_truth.py
"${PYTHON}" scripts/ci/check_top_tier_policy.py
"${PYTHON}" scripts/ci/check_soft_gate_budget.py
"${PYTHON}" scripts/ci/check_parallel_git_ops.py

echo "[LOCAL-GATE] ci guard script tests"
pytest -q tests/ci/test_ci_guard_scripts.py

echo "[LOCAL-GATE] start UI server"
WARM_DB_PATH="${SERVER_DB_PATH}" \
  WARM_SIM_SANDBOX=1 \
  WARM_SKIP_PROVENANCE_GUARD="${WARM_SKIP_PROVENANCE_GUARD:-1}" \
  "${PYTHON}" src/warm_logic/ui/server.py >/tmp/warmlogic_ui_server_local_gate.log 2>&1 &
SERVER_PID=$!
cleanup() {
  kill "${SERVER_PID}" >/dev/null 2>&1 || :
}
trap cleanup EXIT

for _ in {1..60}; do
  if curl -sf "http://127.0.0.1:${WARM_HTTP_PORT}/health/liveness" >/dev/null; then
    READY=1
    break
  fi
  sleep 1
done
if [[ "${READY:-0}" != "1" ]]; then
  echo "[LOCAL-GATE] ERROR: UI server did not become healthy on port ${WARM_HTTP_PORT}" >&2
  tail -n 120 /tmp/warmlogic_ui_server_local_gate.log >&2 || true
  exit 7
fi
curl -sf "http://127.0.0.1:${WARM_HTTP_PORT}/health/liveness" >/dev/null

echo "[LOCAL-GATE] mesh e2e"
WARM_RUN_MESH_E2E=1 pytest -q -W error -ra \
  tests/e2e/test_mesh_sync.py::test_gossip_propagation

echo "[LOCAL-GATE] constitutional e2e"
WARM_UI_BASE_URL="http://127.0.0.1:${WARM_HTTP_PORT}" pytest -q -W error -ra \
  tests/security/test_constitutional_e2e.py::TestConstitutionalE2E::test_e2e_api_guard

if [[ "${RUN_FULL}" == "1" ]]; then
  echo "[LOCAL-GATE] strict full suite (live e2e enabled)"
  STRICT_JUNIT="/tmp/warmlogic_strict_full.junit.xml"
  WARM_RUN_MESH_E2E=1 WARM_UI_BASE_URL="http://127.0.0.1:${WARM_HTTP_PORT}" \
    pytest -n auto -q -W error -ra --junitxml "${STRICT_JUNIT}" "${PYTEST_IGNORE_ARGS[@]}"
  "${PYTHON}" scripts/ci/check_junit_summary.py \
    --junit "${STRICT_JUNIT}" \
    --max-skipped 0 \
    --max-failures 0 \
    --max-errors 0 \
    --min-tests 1
else
  echo "[LOCAL-GATE] skip full strict suite (--no-full)"
fi

echo "[LOCAL-GATE] complete"
