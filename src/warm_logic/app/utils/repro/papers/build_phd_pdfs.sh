#!/usr/bin/env bash
set -euo pipefail

# Build PDFs for all Markdown files in docs/papers/ai_ethics/phd

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PHD_DIR="${ROOT}/docs/papers/ai_ethics/phd"
HDR_TEX="${ROOT}/docs/papers/_shared/tex/unicode_fixes.tex"
SPEC_PATH="${ROOT}/docs/specs/pass_compiler_v0.1.yaml"

if ! command -v pandoc >/dev/null 2>&1; then
  echo "[ERROR] pandoc not found. Install pandoc (e.g., brew install pandoc)." >&2
  exit 1
fi

# Ensure compiler spec is present (SSOT for PASS v0.1)
if [[ ! -f "$SPEC_PATH" ]]; then
  echo "[phd-build] Missing compiler spec: $SPEC_PATH" >&2
  exit 3
fi

shopt -s nullglob
mds=("${PHD_DIR}"/*.md)
if [[ ${#mds[@]} -eq 0 ]]; then
  echo "[phd-build] No Markdown files in ${PHD_DIR}"
  exit 0
fi

for md in "${mds[@]}"; do
  base="${md%.*}"
  out="${base}.pdf"
  echo "[phd-build] Building $(basename "$out")"
  pandoc "$md" \
    --from markdown+yaml_metadata_block \
    --pdf-engine=xelatex \
    --include-in-header="$HDR_TEX" \
    --resource-path="$PHD_DIR" \
    -V geometry:margin=1in -V linkcolor:blue \
    -V mainfont="Times New Roman" \
    -o "$out"
done

echo "[phd-build] Done. PDFs written next to their Markdown sources."
