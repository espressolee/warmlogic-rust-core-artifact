#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_ID=${1:-"RUN_OSV2_20260103T080126Z-os_v2"}

echo "Running OS v2 artifact CI validation for ${RUN_ID}"

# osctl sanity (run+verify) using sample config/events
bash "${ROOT}/scripts/ci/osctl_sanity.sh" "${RUN_ID}"

# Regenerate figures + replay/verify + bundle + release notes
bash "${ROOT}/scripts/make_os_v2_figures.sh" "${RUN_ID}"

echo "Validation complete. Bundled hash stored in docs/papers/reflective_os/os_v2/release/RELEASE_NOTES.md and artifact badge documents."
