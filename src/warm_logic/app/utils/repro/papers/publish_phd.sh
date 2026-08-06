#!/usr/bin/env bash
set -euo pipefail

# Publish refreshed PhD_Combined.pdf to releases with a date stamp and latest symlink.
# Usage: scripts/papers/publish_phd.sh [--date YYYYMMDD]

DATE="$(date +%Y%m%d)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --date) DATE="$2"; shift 2;;
    -h|--help) echo "Usage: $0 [--date YYYYMMDD]"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/docs/papers/ai_ethics/phd/PhD_Combined.pdf"
DEST_DIR="$ROOT/docs/papers/releases/phd"

if [[ ! -f "$SRC" ]]; then
  echo "[phd-publish] Missing PhD combined PDF: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
DEST="$DEST_DIR/PhD_Combined_${DATE}.pdf"
cp -f "$SRC" "$DEST"
ln -sfn "$(basename "$DEST")" "$DEST_DIR/PhD_Combined_latest.pdf"
echo "[phd-publish] -> $DEST"
