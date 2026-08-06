#!/usr/bin/env bash
set -euo pipefail

# Generate SHA256 checksums for release PDFs and bundles under docs/papers/releases.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$ROOT/docs/papers/releases"
LEDGER_SRC="$ROOT/docs/research/Error_and_Counterexample_Ledger_v1.md"
LEDGER_DST="$OUT_DIR/Error_and_Counterexample_Ledger_v1.md"
INDEX_FILE="$OUT_DIR/Error_and_Counterexamples_Index.md"

# Ensure ledger is present in releases before checksumming.
if [[ -f "$LEDGER_SRC" ]]; then
  cp "$LEDGER_SRC" "$LEDGER_DST"
else
  echo "[checksums] Missing ledger source: $LEDGER_SRC" >&2
  exit 1
fi
TARGETS=(
  "$OUT_DIR/papers"/*.pdf
  "$OUT_DIR/bundles"/*.zip
  "$OUT_DIR/figures"/*.zip
  "$OUT_DIR/reviewer_packets"/*.zip
  "$OUT_DIR/Error_and_Counterexamples_Index.md"
  "$OUT_DIR/Error_and_Counterexample_Ledger_v1.md"
)

DEST="$OUT_DIR/CHECKSUMS_SHA256.txt"
> "$DEST"
shopt -s nullglob
for pattern in "${TARGETS[@]}"; do
  for f in $pattern; do
    sha256sum "$f" >> "$DEST" || shasum -a 256 "$f" >> "$DEST"
  done
done
echo "[checksums] Wrote $DEST"
