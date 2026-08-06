#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
THEMES_DIR="$ROOT/docs/papers/themes"

build_md() {
  local md="$1" out_pdf="$2"
  mkdir -p "$(dirname "$out_pdf")"
  pandoc "$md" \
    --from markdown+yaml_metadata_block \
    --pdf-engine=xelatex \
    --include-in-header="$ROOT/docs/papers/_shared/tex/unicode_fixes.tex" \
    -V geometry:margin=1in -V linkcolor:blue \
    -V mainfont="Times New Roman" \
    -o "$out_pdf"
}

build_tex() {
  local tex="$1" out_dir="$2"
  mkdir -p "$out_dir"
  (cd "$(dirname "$tex")" && latexmk -pdf -quiet -outdir="$out_dir" "$(basename "$tex")") || {
    echo "[warn] latexmk failed for $tex" >&2
    return 1
  }
}

for d in "$THEMES_DIR"/2025_theme{1,2,3,4,5}; do
  [[ -d "$d" ]] || continue
  name=$(basename "$d")
  outdir="$d/out"
  md="$d/${name/_paper/_paper}.md" # default guess
  # normalize known names
  case "$name" in
    2025_theme1) md="$d/theme1_paper.md" ; tex="$d/theme1.tex";;
    2025_theme2) md="$d/theme2_paper.md" ; tex="$d/theme2.tex";;
    2025_theme3) md="$d/theme3_paper.md" ; tex="$d/theme3.tex";;
    2025_theme4) md="$d/theme4_paper.md" ; tex="$d/theme4.tex";;
    2025_theme5) md="$d/theme5_paper.md" ; tex="$d/theme5.tex";;
  esac
  if [[ -f "$md" ]]; then
    out_pdf="$outdir/${name}.pdf"
    echo "[theme-build] MD -> $out_pdf"
    build_md "$md" "$out_pdf" || true
  elif [[ -n "${tex:-}" && -f "$tex" ]]; then
    echo "[theme-build] TeX -> $outdir"
    build_tex "$tex" "$outdir" || true
  else
    echo "[theme-build] skip $name (no md/tex found)"
  fi
done

echo "[theme-build] Done"
