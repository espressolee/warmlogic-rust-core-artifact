#!/usr/bin/env bash
set -euo pipefail

# Generate SHA256 checksums for figure bundles under releases/figures only.
# Writes: docs/papers/releases/figures/CHECKSUMS_SHA256.txt

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$ROOT/docs/papers/releases/figures"
DEST="$OUT_DIR/CHECKSUMS_SHA256.txt"

> "$DEST"
shopt -s nullglob

# Only hash dated zips (avoid *_latest*.zip symlink churn)
for f in "$OUT_DIR"/Paper*_Figures_*.zip; do
  if [[ -f "$f" ]]; then
    if command -v sha256sum >/dev/null 2>&1; then
      sha256sum "$f" >> "$DEST"
    else
      shasum -a 256 "$f" >> "$DEST"
    fi
  fi
done

echo "[fig-checksums] Wrote $DEST"
