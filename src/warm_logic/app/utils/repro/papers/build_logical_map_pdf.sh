#!/usr/bin/env bash
set -euo pipefail

# Build a 1-page PDF for the Chapter X Logical Map from the SVG figure.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SVG="${ROOT}/docs/papers/ai_ethics/phd/figures/chapter_x_logical_map.svg"
OUT_DIR="${ROOT}/docs/papers/ai_ethics/phd/out"
OUT_PDF="${OUT_DIR}/ChapterX_Logical_Map.pdf"
OUT_PNG="${OUT_DIR}/ChapterX_Logical_Map.png"

if [[ ! -f "$SVG" ]]; then
  echo "[logical-map] Missing SVG: $SVG" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

if command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -f pdf -o "$OUT_PDF" "$SVG"
  rsvg-convert -f png -o "$OUT_PNG" "$SVG"
  echo "[logical-map] Wrote $OUT_PDF and $OUT_PNG (librsvg)"
else
  # Fallback via pandoc+xelatex: wrap the SVG in a minimal MD and render
  if ! command -v pandoc >/dev/null 2>&1; then
    echo "[logical-map] Neither rsvg-convert nor pandoc present." >&2
    exit 2
  fi
  TMP_MD="${OUT_DIR}/_logical_map_tmp.md"
  echo "![](${SVG})" > "$TMP_MD"
  pandoc "$TMP_MD" --pdf-engine=xelatex -o "$OUT_PDF"
  rm -f "$TMP_MD"
  echo "[logical-map] Wrote $OUT_PDF (pandoc fallback)"
fi
