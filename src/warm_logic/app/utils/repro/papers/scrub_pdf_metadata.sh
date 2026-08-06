#!/usr/bin/env bash
set -euo pipefail

# Scrub common PDF metadata fields using Ghostscript (gs).
# Usage: scripts/papers/scrub_pdf_metadata.sh <in.pdf> <out.pdf>

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <in.pdf> <out.pdf>" >&2
  exit 2
fi

IN="$1"
OUT="$2"

if ! command -v gs >/dev/null 2>&1; then
  echo "[scrub] Ghostscript (gs) not found" >&2
  exit 1
fi

gs -q -dNOPAUSE -dBATCH \
  -sDEVICE=pdfwrite \
  -dCompatibilityLevel=1.4 \
  -dDetectDuplicateImages \
  -dCompressFonts=true \
  -sOutputFile="$OUT" \
  -c "[ /Title () /Author () /Creator () /Producer () /Subject () /Keywords () /CreationDate () /ModDate () /DOCINFO pdfmark" \
  -f "$IN"

echo "[scrub] Wrote $OUT"
