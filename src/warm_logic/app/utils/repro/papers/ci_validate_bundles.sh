#!/usr/bin/env bash
set -euo pipefail

# CI wrapper for validating all submission bundles under a directory (default: out/submission)
# Uses scripts/papers/validate_submission_bundle.py

DIR="out/submission"

usage() {
  echo "Usage: $0 [--dir <path>]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) DIR="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ ! -d "$DIR" ]]; then
  echo "[info] No directory: $DIR (skipping)"
  exit 0
fi

FIRST_ZIP=$(find "$DIR" -type f -name '*.zip' | head -n 1 || true)
if [[ -z "${FIRST_ZIP:-}" ]]; then
  echo "[info] No bundles (*.zip) found under $DIR"
  exit 0
fi

echo "[info] Validating bundles under $DIR"
python3 scripts/papers/validate_submission_bundle.py "$DIR"
