#!/usr/bin/env bash
set -euo pipefail

# Generate a compat drift report for the current LTS (or COMPAT_AGAINST override).
# Usage: bash scripts/ci/compat_generate_report.sh [AGAINST]

AGAINST="${1:-${COMPAT_AGAINST:-}}"
INDEX_PATH="spec/compat/INDEX.json"

if [[ -z "${AGAINST}" ]]; then
  if [[ -f "${INDEX_PATH}" ]]; then
    AGAINST=$(python - << 'PY'
import json,sys
with open('spec/compat/INDEX.json','r',encoding='utf-8') as f:
    idx=json.load(f)
print(idx.get('current_lts') or next(iter((idx.get('baselines') or {}).keys()), 'unknown'))
PY
)
  else
    echo "::error::Missing ${INDEX_PATH} and COMPAT_AGAINST not set" >&2
    exit 2
  fi
fi

REPORT="out/compat/report_${AGAINST}.json"
mkdir -p out/compat

echo "Generating compat report for ${AGAINST} -> ${REPORT}"
python -m warm_logic.compat.smoke --against "${AGAINST}" --index "${INDEX_PATH}" --write-report "${REPORT}" || true

if [[ -f "${REPORT}" ]]; then
  echo "Compat report written: ${REPORT}"
else
  echo "::warning::Compat report not created"
fi

echo "REPORT_PATH=${REPORT}" >> "$GITHUB_OUTPUT" 2>/dev/null || true
