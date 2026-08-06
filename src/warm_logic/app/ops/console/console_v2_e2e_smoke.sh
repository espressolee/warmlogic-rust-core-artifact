#!/usr/bin/env bash
# Console v2 E2E smoke: osctl run (optional) + CE ledger update + Console v2 API checks.
set -euo pipefail

# -----------------------------------------------------------------------------
# Config / env
# -----------------------------------------------------------------------------
SKIP_API="${CONSOLE_E2E_SKIP_API:-0}"
CONSOLE_V2_BASE="${CONSOLE_V2_BASE:-}"
if [[ "${SKIP_API}" != "1" ]]; then
  if [[ -z "${CONSOLE_V2_BASE}" ]]; then
    echo "[ERROR] CONSOLE_V2_BASE must be set (e.g., https://console.example.com)" >&2
    echo "        Or set CONSOLE_E2E_SKIP_API=1 to skip Console API calls." >&2
    exit 1
  fi
fi

CONSOLE_V2_TOKEN="${CONSOLE_V2_TOKEN:-}"
CONSOLE_V2_API_KEY="${CONSOLE_V2_API_KEY:-}"

ORG_ID="${CONSOLE_V2_ORG_ID:-demo-org}"
TENANT_ID="${CONSOLE_V2_TENANT_ID:-team-a}"
RUN_ID="${CONSOLE_V2_RUN_ID:-RUN_CONSOLE_E2E_$(date +%s)}"
API_PREFIX="${CONSOLE_V2_API_PREFIX:-/api/v1}"  # current backend serves v1 paths; update when v2 stabilises

RUN_ROOT_BASE="${CONSOLE_V2_RUN_ROOT:-out/console_v2_e2e}"
RUN_ROOT="${RUN_ROOT_BASE}/${RUN_ID}"
MANIFEST_PATH="${CONSOLE_V2_MANIFEST_PATH:-${RUN_ROOT}/run_manifest.json}"
BUNDLE_PATH="${CONSOLE_V2_BUNDLE_PATH:-${RUN_ROOT}/bundle/run_bundle.zip}"
LEDGER_DIR="${CONSOLE_E2E_LEDGER_DIR:-${RUN_ROOT_BASE}/_ledgers}"
EXTERNAL_REPRO_LEDGER_PATH="${CONSOLE_E2E_EXTERNAL_REPRO_LEDGER_PATH:-${LEDGER_DIR}/External_Repro_Status_v1.json}"
COUNTEREXAMPLES_LEDGER_PATH="${CONSOLE_E2E_COUNTEREXAMPLES_LEDGER_PATH:-${LEDGER_DIR}/Counterexamples_v1.json}"
READONLY_FLAG_PATH="${CONSOLE_E2E_READONLY_FLAG_PATH:-${LEDGER_DIR}/read_only.flag}"
OSCTL_CONFIG="${CONSOLE_E2E_OSCTL_CONFIG:-configs/demo/console_v2_e2e.yaml}"
OSCTL_EVENTS="${CONSOLE_E2E_OSCTL_EVENTS:-docs/papers/reflective_os/os_v2/event_log_sample.jsonl}"
OSCTL_SCHEMAS_ROOT="${CONSOLE_E2E_OSCTL_SCHEMAS_ROOT:-docs/papers/reflective_os/os_v2/json_schemas}"
ATTEMPT="${CONSOLE_E2E_ATTEMPT:-0}"
SKIP_RUN="${CONSOLE_E2E_SKIP_RUN:-0}"
SKIP_LEDGER="${CONSOLE_E2E_SKIP_LEDGER:-0}"
ALLOW_OVERWRITE="${CONSOLE_E2E_ALLOW_OVERWRITE:-1}"
SYNC_TO_CONSOLE_ROOT="${CONSOLE_E2E_SYNC_TO_CONSOLE_ROOT:-1}"
CONSOLE_RUN_ROOT="${CONSOLE_E2E_CONSOLE_RUN_ROOT:-out/osctl_runs}"
EMIT_SLI="${CONSOLE_E2E_EMIT_SLI:-1}"

HEADER_AUTH=()
if [[ -n "${CONSOLE_V2_TOKEN}" ]]; then
  HEADER_AUTH+=( -H "Authorization: Bearer ${CONSOLE_V2_TOKEN}" )
fi
if [[ -n "${CONSOLE_V2_API_KEY}" ]]; then
  HEADER_AUTH+=( -H "X-API-Key: ${CONSOLE_V2_API_KEY}" )
fi

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
curl_json() {
  local method="$1"; shift
  local url="$1"; shift
  local tmp_body
  tmp_body="$(mktemp)"

  http_code=$(
    curl -sS -X "${method}" "${CONSOLE_V2_BASE}${url}" \
      "${HEADER_AUTH[@]}" \
      -H "Accept: application/json" \
      -o "${tmp_body}" \
      -w '%{http_code}'
  )

  if [[ "${http_code}" != "200" ]]; then
    echo "[ERROR] ${method} ${url} -> HTTP ${http_code}" >&2
    echo "Body:" >&2
    cat "${tmp_body}" >&2
    rm -f "${tmp_body}"
    return 1
  fi

  cat "${tmp_body}"
  rm -f "${tmp_body}"
}

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "[ERROR] required file missing: $1" >&2
    exit 1
  fi
}

resolve_manifest() {
  # Try common paths where osctl run may have written the manifest.
  local candidates=(
    "${MANIFEST_PATH}"
    "${RUN_ROOT}/run_manifest.json"
    "${RUN_ROOT}/${RUN_ID}/run_manifest.json"
  )
  for p in "${candidates[@]}"; do
    if [[ -f "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

resolve_bundle() {
  # Prefer zip bundle, fallback to JSON manifest if present.
  local candidates=(
    "${BUNDLE_PATH}"
    "${RUN_ROOT}/bundle/osctl_bundle.zip"
    "${RUN_ROOT}/${RUN_ID}/bundle/osctl_bundle.zip"
    "${RUN_ROOT}/bundle_manifest.json"
    "${RUN_ROOT}/${RUN_ID}/bundle_manifest.json"
  )
  for p in "${candidates[@]}"; do
    if [[ -f "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

# -----------------------------------------------------------------------------
# Step 1: osctl run (optional)
# -----------------------------------------------------------------------------
if [[ "${SKIP_RUN}" != "1" ]]; then
  echo "[INFO] running osctl: RUN_ID=${RUN_ID}, ORG_ID=${ORG_ID}, TENANT_ID=${TENANT_ID}"
  # Do NOT pre-create RUN_ROOT: osctl enforces idempotency by failing if the run_dir exists.
  mkdir -p "${RUN_ROOT_BASE}"
  mkdir -p "${LEDGER_DIR}"

  export OSCTL_EXTERNAL_REPRO_LEDGER_PATH="${EXTERNAL_REPRO_LEDGER_PATH}"
  export OSCTL_CE_LEDGER_PATH="${COUNTEREXAMPLES_LEDGER_PATH}"
  export OSCTL_READONLY_FLAG_PATH="${READONLY_FLAG_PATH}"

  OSCTL_ALLOW_OVERWRITE_FLAG=()
  if [[ "${ALLOW_OVERWRITE}" == "1" ]]; then
    OSCTL_ALLOW_OVERWRITE_FLAG+=( --allow-overwrite )
  fi

  python -m warm_logic.osctl.cli run \
    --config "${OSCTL_CONFIG}" \
    --events "${OSCTL_EVENTS}" \
    --run-id "${RUN_ID}" \
    --attempt "${ATTEMPT}" \
    --org-id "${ORG_ID}" \
    --tenant-id "${TENANT_ID}" \
    --out-dir "${RUN_ROOT_BASE}" \
    --schemas-root "${OSCTL_SCHEMAS_ROOT}" \
    "${OSCTL_ALLOW_OVERWRITE_FLAG[@]}"
else
  echo "[INFO] skipping osctl run (CONSOLE_E2E_SKIP_RUN=1)"
fi

if ! { [[ "${SKIP_RUN}" == "1" ]] && [[ "${SKIP_LEDGER}" == "1" ]]; }; then
  if ! MANIFEST_PATH_RESOLVED="$(resolve_manifest)"; then
    echo "[ERROR] manifest not found in expected paths under ${RUN_ROOT}" >&2
    exit 1
  fi
  MANIFEST_PATH="${MANIFEST_PATH_RESOLVED}"

  if BUNDLE_PATH_RESOLVED="$(resolve_bundle)"; then
    BUNDLE_PATH="${BUNDLE_PATH_RESOLVED}"
  fi
fi

# -----------------------------------------------------------------------------
# Step 2: update CE ledger (optional)
# -----------------------------------------------------------------------------
if [[ "${SKIP_LEDGER}" != "1" ]]; then
  mkdir -p "${LEDGER_DIR}"

  # If we just executed osctl run, the ledger update already occurred inside osctl.
  # In that case, only validate that the ledger contains the run_id entry.
  if [[ "${SKIP_RUN}" != "1" ]]; then
    echo "[INFO] validating External_Repro ledger contains ${RUN_ID}: ${EXTERNAL_REPRO_LEDGER_PATH}"
    RUN_ID="${RUN_ID}" EXTERNAL_REPRO_LEDGER_PATH="${EXTERNAL_REPRO_LEDGER_PATH}" python - <<'PY'
import json, os
from pathlib import Path

run_id = os.environ["RUN_ID"]
ledger_path = Path(os.environ["EXTERNAL_REPRO_LEDGER_PATH"])
if not ledger_path.exists():
    raise SystemExit(f"[ERROR] ledger missing: {ledger_path}")
data = json.loads(ledger_path.read_text(encoding="utf-8"))
if not isinstance(data, list):
    raise SystemExit(f"[ERROR] ledger not a list: {ledger_path}")
if not any(e.get("run_id") == run_id for e in data):
    raise SystemExit(f"[ERROR] ledger missing run_id entry: {run_id}")
print(f"[OK] ledger contains run_id={run_id} ({ledger_path})")
PY
  else
    echo "[INFO] updating External_Repro ledger at ${EXTERNAL_REPRO_LEDGER_PATH}"
    UPDATE_ARGS=(
      --manifest-path "${MANIFEST_PATH}"
      --ledger-path "${EXTERNAL_REPRO_LEDGER_PATH}"
      --ce-ledger "${COUNTEREXAMPLES_LEDGER_PATH}"
      --readonly-flag "${READONLY_FLAG_PATH}"
      --run-id "${RUN_ID}"
      --org-id "${ORG_ID}"
      --tenant-id "${TENANT_ID}"
      --attempt "${ATTEMPT}"
    )
    # Pass bundle manifest JSON only if we found one.
    if [[ -n "${BUNDLE_PATH:-}" && "${BUNDLE_PATH##*.}" =~ ^(json|jsonl)$ ]]; then
      UPDATE_ARGS+=( --bundle-manifest "${BUNDLE_PATH}" )
    fi
    python scripts/evidenceos/update_ledger_from_run.py "${UPDATE_ARGS[@]}"
  fi

  if [[ -f "spec/schema/evidence/external_repro_ledger_v1.schema.json" ]]; then
    check-jsonschema --schemafile spec/schema/evidence/external_repro_ledger_v1.schema.json "${EXTERNAL_REPRO_LEDGER_PATH}"
  fi
else
  echo "[INFO] skipping ledger update (CONSOLE_E2E_SKIP_LEDGER=1)"
fi

# -----------------------------------------------------------------------------
# Step 2.5: sync run artifacts into console run_root + emit SLI stub
# -----------------------------------------------------------------------------
if ! { [[ "${SKIP_RUN}" == "1" ]] && [[ "${SKIP_LEDGER}" == "1" ]]; }; then
  if [[ "${SYNC_TO_CONSOLE_ROOT}" == "1" ]]; then
    if [[ "${RUN_ROOT_BASE}" == "${CONSOLE_RUN_ROOT}" ]]; then
      echo "[INFO] run root already matches console run_root; skipping sync (${CONSOLE_RUN_ROOT})"
    else
      echo "[INFO] syncing run artifacts into console run_root: ${CONSOLE_RUN_ROOT}"
      SRC_ROOT="${RUN_ROOT_BASE}" DEST_ROOT="${CONSOLE_RUN_ROOT}" SYNC_CE_LEDGER=0 \
        bash scripts/console/sync_runs_to_console_root.sh "${RUN_ID}"
    fi
  fi

  if [[ "${EMIT_SLI}" == "1" ]]; then
    echo "[INFO] computing runtime SLI for console (out/metrics/runtime_sli_${RUN_ID}.json)"
    RUN_ID="${RUN_ID}" RUN_ROOT="${CONSOLE_RUN_ROOT}" METRICS_ROOT="out/metrics" CE_LEDGER_PATH="${COUNTEREXAMPLES_LEDGER_PATH}" \
      bash scripts/console/emit_sli_stub_from_run.sh
  fi
fi

# -----------------------------------------------------------------------------
# Step 3: Console v2 API calls
# -----------------------------------------------------------------------------
if [[ "${SKIP_API}" == "1" ]]; then
  echo "[INFO] skipping Console API calls (CONSOLE_E2E_SKIP_API=1)"
  echo "[OK] Console v2 E2E smoke passed (no API): RUN_ID=${RUN_ID}, ORG_ID=${ORG_ID}, TENANT_ID=${TENANT_ID}"
  exit 0
fi

echo "[INFO] calling Console API (runs/ce-ledger) prefix=${API_PREFIX}"

# Run list
runs_json="$(curl_json GET "${API_PREFIX}/runs")"
echo "${runs_json}" | jq -e '.items | length > 0' >/dev/null \
  || { echo "[ERROR] no runs in run list" >&2; exit 1; }

# Run detail
run_json="$(curl_json GET "${API_PREFIX}/runs/${RUN_ID}")"
echo "${run_json}" | jq -e --arg rid "${RUN_ID}" '.run_id == $rid' >/dev/null \
  || { echo "[ERROR] run_id mismatch in run detail" >&2; exit 1; }
echo "${run_json}" | jq -e '.status? | (. == null or type == "string")' >/dev/null \
  || { echo "[ERROR] status invalid in run detail" >&2; exit 1; }
echo "${run_json}" | jq -e '.hash? | (. == null or type == "string")' >/dev/null \
  || { echo "[ERROR] hash invalid in run detail" >&2; exit 1; }
if [[ "${EMIT_SLI}" == "1" ]] && ! { [[ "${SKIP_RUN}" == "1" ]] && [[ "${SKIP_LEDGER}" == "1" ]]; }; then
  echo "${run_json}" | jq -e '.sli_warning == null' >/dev/null \
    || { echo "[ERROR] expected sli_warning=null (SLI should be present for full E2E)" >&2; exit 1; }
fi

# CE (v1: /api/v1/ce-ledger)
ce_json="$(curl_json GET "${API_PREFIX}/ce-ledger")"
echo "${ce_json}" | jq -e '.items | type == "array"' >/dev/null \
  || { echo "[ERROR] CE ledger not array" >&2; exit 1; }

echo "[OK] Console v2 E2E smoke passed: RUN_ID=${RUN_ID}, ORG_ID=${ORG_ID}, TENANT_ID=${TENANT_ID}"
