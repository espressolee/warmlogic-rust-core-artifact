#!/usr/bin/env bash
# Emit a minimal SLI JSON for a given run, to be read by console backend.
set -euo pipefail

RUN_ID="${RUN_ID:-}"
RUN_ROOT="${RUN_ROOT:-out/osctl_runs}"
METRICS_ROOT="${METRICS_ROOT:-out/metrics}"
CE_LEDGER_PATH="${CE_LEDGER_PATH:-ledger/CE_Ledger_v1.jsonl}"

if [[ -z "${RUN_ID}" ]]; then
  echo "Usage: RUN_ID=<run_id> [RUN_ROOT=out/osctl_runs] [METRICS_ROOT=out/metrics] [CE_LEDGER_PATH=ledger/CE_Ledger_v1.jsonl] $0" >&2
  exit 1
fi

mkdir -p "${METRICS_ROOT}"

python scripts/metrics/compute_runtime_sli.py \
  --runs-root "${RUN_ROOT}" \
  --run-id "${RUN_ID}" \
  --out-dir "${METRICS_ROOT}" \
  --ce-ledger "${CE_LEDGER_PATH}"
