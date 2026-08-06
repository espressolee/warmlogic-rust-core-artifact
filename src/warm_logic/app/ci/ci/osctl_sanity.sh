#!/usr/bin/env bash
set -euo pipefail

# Default demo org/tenant so osctl can run in CI without extra env.
: "${OSCTL_DEFAULT_ORG_ID:=demo-org}"
: "${OSCTL_DEFAULT_TENANT_ID:=demo-tenant}"
# Allow legacy demo flow unless explicitly overridden.
: "${OSCTL_ALLOW_LEGACY_DEMO:=1}"
export OSCTL_DEFAULT_ORG_ID OSCTL_DEFAULT_TENANT_ID OSCTL_ALLOW_LEGACY_DEMO

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_ID="${1:-OSCTL_CI_TEST_${GITHUB_RUN_ID:-$(date +%s)}}"
OUT_DIR="${ROOT}/out/osctl_runs_ci"
LEDGER_DIR="${OUT_DIR}/_ledgers"
export OSCTL_EXTERNAL_REPRO_LEDGER_PATH="${LEDGER_DIR}/External_Repro_Status_v1.json"
export OSCTL_CE_LEDGER_PATH="${LEDGER_DIR}/Counterexamples_v1.json"
export OSCTL_READONLY_FLAG_PATH="${LEDGER_DIR}/read_only.flag"
mkdir -p "${LEDGER_DIR}"
SCHEMAS_ROOT="${ROOT}/docs/papers/reflective_os/os_v2/json_schemas"
CONFIG="${ROOT}/docs/papers/reflective_os/os_v2/os_v2_config.yaml"
EVENTS="${ROOT}/docs/papers/reflective_os/os_v2/event_log_sample.jsonl"

echo "[osctl][ci] run_id=${RUN_ID}"
rm -rf "${OUT_DIR:?}/${RUN_ID}"

python -m warm_logic.osctl.cli run \
  --config "${CONFIG}" \
  --events "${EVENTS}" \
  --out-dir "${OUT_DIR}" \
  --schemas-root "${SCHEMAS_ROOT}" \
  --run-id "${RUN_ID}" \
  --attempt 0 \
  --org-id "${OSCTL_DEFAULT_ORG_ID}" \
  --tenant-id "${OSCTL_DEFAULT_TENANT_ID}" \
  --no-bundle

python -m warm_logic.osctl.cli verify \
  --run-id "${RUN_ID}" \
  --out-dir "${OUT_DIR}" \
  --schemas-root "${SCHEMAS_ROOT}"

# Compute SLI metrics for console/observability
python "${ROOT}/scripts/metrics/compute_runtime_sli.py" \
  --runs-root "${OUT_DIR}" \
  --run-id "${RUN_ID}" \
  --out-dir "${ROOT}/out/metrics" \
  --ce-ledger "${OSCTL_CE_LEDGER_PATH}"

echo "[osctl][ci] sanity PASS for ${RUN_ID}"
