#!/usr/bin/env bash
set -euo pipefail

# Accept current runtime snapshot as the new compat baseline and optionally update index.
# Usage: bash scripts/ci/compat_accept_baseline.sh AGAINST [BASELINE_JSON]

AGAINST="${1:-}"
BASELINE_PATH_INPUT="${2:-}"
INDEX_PATH="spec/compat/INDEX.json"

if [[ -z "${AGAINST}" ]]; then
  echo "::error::Usage: $0 AGAINST [BASELINE_JSON]" >&2
  exit 2
fi

ARGS=("--against" "${AGAINST}" "--index" "${INDEX_PATH}" "--accept")

# Default baseline location within repo spec tree
DEFAULT_BASELINE_PATH="spec/compat/v${AGAINST}/kernel_tick.json"
BASELINE_PATH="${BASELINE_PATH_INPUT:-${DEFAULT_BASELINE_PATH}}"
mkdir -p "$(dirname "${BASELINE_PATH}")"
ARGS+=("--baseline" "${BASELINE_PATH}" "--update-index")

echo "Accepting baseline for ${AGAINST}"
python -m warm_logic.compat.smoke "${ARGS[@]}"

# Show changed files (for CI logs)
git status --porcelain || true

echo "Baseline acceptance completed"
