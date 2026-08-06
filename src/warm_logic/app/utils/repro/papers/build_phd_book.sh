#!/usr/bin/env bash
set -euo pipefail

# Build a single combined PDF for PhD chapters W, X, Y, Z + Conclusion

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PHD_DIR="${ROOT}/docs/papers/ai_ethics/phd"
HDR_TEX="${ROOT}/docs/papers/_shared/tex/unicode_fixes.tex"
OUT_PDF="${PHD_DIR}/PhD_Combined.pdf"
SPEC_PATH="${ROOT}/docs/specs/pass_compiler_v0.1.yaml"

FILES=(
  "${PHD_DIR}/PhD_Cover.md"
  "${PHD_DIR}/PhD_Combined_Opening.md"
  "${PHD_DIR}/Chapter_W_Comparative_Evaluation.md"
  "${PHD_DIR}/Chapter_X_Moral_Finality_Theory_and_Structural_Evidence.md"
  "${PHD_DIR}/Chapter_Y_Design_Constraints.md"
  "${PHD_DIR}/Chapter_Z_Indicators.md"
  "${PHD_DIR}/Appendix_Templates_Indicator_Mapping_Sheets.md"
  "${PHD_DIR}/Appendix_A_Filled_Example_Org.md"
  "${PHD_DIR}/Appendix_B_Filled_Example_Platform.md"
  "${PHD_DIR}/Conclusion.md"
)

for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "[phd-book] Missing file: $f" >&2
    exit 2
  fi
done

# Ensure compiler spec is present (SSOT for PASS v0.1)
if [[ ! -f "$SPEC_PATH" ]]; then
  echo "[phd-book] Missing compiler spec: $SPEC_PATH" >&2
  exit 3
fi

if ! command -v pandoc >/dev/null 2>&1; then
  echo "[ERROR] pandoc not found. Install pandoc (e.g., brew install pandoc)." >&2
  exit 1
fi

echo "[phd-book] Building combined PDF → $OUT_PDF"
pandoc "${FILES[@]}" \
  --from markdown+yaml_metadata_block \
  --toc --toc-depth=2 \
  --pdf-engine=xelatex \
  --include-in-header="$HDR_TEX" \
  --resource-path="$PHD_DIR" \
  -V geometry:margin=1in -V linkcolor:blue \
  -V mainfont="Times New Roman" \
  -o "$OUT_PDF"

echo "[phd-book] Done: $OUT_PDF"
