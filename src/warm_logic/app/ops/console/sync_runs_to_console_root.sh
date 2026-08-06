#!/usr/bin/env bash
# Sync osctl runs/ledger/metrics into the console backend roots.
set -euo pipefail

SRC_ROOT="${SRC_ROOT:-out/console_v2_e2e}"
DEST_ROOT="${DEST_ROOT:-out/osctl_runs}"
LEDGER_SRC="${LEDGER_SRC:-out/console_v2_e2e/CE_Ledger_v1.jsonl}"
LEDGER_DEST="${LEDGER_DEST:-ledger/pilots/TeamA/CE_Ledger_v1.jsonl}"
SYNC_CE_LEDGER="${SYNC_CE_LEDGER:-0}"
RUN_ID="${RUN_ID:-}"

usage() {
  cat <<'EOF'
Usage: sync_runs_to_console_root.sh [RUN_ID]
Environment:
  SRC_ROOT    source run root (default: out/console_v2_e2e)
  DEST_ROOT   console run root (default: out/osctl_runs)
  LEDGER_SRC  source CE ledger (default: out/console_v2_e2e/CE_Ledger_v1.jsonl)
  LEDGER_DEST console CE ledger (default: ledger/pilots/TeamA/CE_Ledger_v1.jsonl)
  SYNC_CE_LEDGER  set to 1 to copy CE ledger (default: 0; off to avoid clobbering local pilot files)
If RUN_ID is provided, only that run is synced; otherwise all runs under SRC_ROOT are copied.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -n "${1:-}" ]]; then
  RUN_ID="$1"
fi

mkdir -p "${DEST_ROOT}"

sync_run() {
  local rid="$1"
  local src="${SRC_ROOT}/${rid}"
  local dst="${DEST_ROOT}/${rid}"
  if [[ ! -d "${src}" ]]; then
    echo "[WARN] run not found: ${src}" >&2
    return
  fi
  echo "[INFO] syncing run ${rid} -> ${dst}"
  rsync -a --delete "${src}/" "${dst}/"
}

if [[ -n "${RUN_ID}" ]]; then
  sync_run "${RUN_ID}"
else
  for d in "${SRC_ROOT}"/*; do
    [[ -d "$d" ]] || continue
    sync_run "$(basename "$d")"
  done
fi

# Sync CE ledger if present
if [[ "${SYNC_CE_LEDGER}" == "1" ]]; then
  if [[ -f "${LEDGER_SRC}" ]]; then
    mkdir -p "$(dirname "${LEDGER_DEST}")"
    cp "${LEDGER_SRC}" "${LEDGER_DEST}"
    echo "[INFO] synced CE ledger to ${LEDGER_DEST}"
  else
    echo "[WARN] CE ledger not found at ${LEDGER_SRC}; skipped" >&2
  fi
else
  echo "[INFO] skipping CE ledger sync (SYNC_CE_LEDGER=${SYNC_CE_LEDGER})"
fi
