#!/usr/bin/env bash
set -euo pipefail

# Export the public OS v2 sanity bundle from the private SSOT to the WarmLogic-OSS repo.
# Usage: scripts/release/export_public_osv2_sanity_bundle.sh [DEST_DIR]
# Default DEST_DIR: ../WarmLogic-OSS/docs/research/eval/Public_OSV2_Sanity_v1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SRC_DIR="${REPO_ROOT}/docs/research/eval/Public_OSV2_Sanity_Source_v1"
DEST_DIR="${1:-${REPO_ROOT}/../WarmLogic-OSS/docs/research/eval/Public_OSV2_Sanity_v1}"

echo "[export] SRC=${SRC_DIR}"
echo "[export] DEST=${DEST_DIR}"

mkdir -p "${DEST_DIR}"

cp "${SRC_DIR}/config_osv2_sanity.yaml" "${DEST_DIR}/" || true
cp "${SRC_DIR}/event_log_sanity.jsonl" "${DEST_DIR}/" || true
cp "${SRC_DIR}/expected_results.json" "${DEST_DIR}/" || true

# External-facing README: use source README as a baseline
if [ -f "${SRC_DIR}/README_public.md" ]; then
  cp "${SRC_DIR}/README_public.md" "${DEST_DIR}/README.md"
else
  cp "${SRC_DIR}/README.md" "${DEST_DIR}/README.md"
fi

# Record the source commit from the main (private) repo
( cd "${REPO_ROOT}" && git rev-parse HEAD ) > "${DEST_DIR}/SOURCE_COMMIT.txt"

echo "[export] Done. Files in ${DEST_DIR}:"
ls -1 "${DEST_DIR}"
