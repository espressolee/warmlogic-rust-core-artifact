#!/usr/bin/env bash
set -euo pipefail

# Build kappa summary and disagreement heatmap from coding_labels_wide.csv
# Uses:
#   - scripts/calc_kappa_external_coder.py
#   - scripts/render_disagreement_heatmap.py
#
# Outputs:
#   - out/kappa_summary.txt (stdout copy) and/or JSON if script supports
#   - figures/fig_disagreement_heatmap.png
#
# Usage:
#   ./scripts/papers/build_kappa_and_heatmap.sh \
#     docs/papers/ai_ethics/2026_moral_finality_measurement_kit/src/coding_labels_wide.csv \
#     docs/papers/ai_ethics/2026_moral_finality_measurement_kit/figures/fig_disagreement_heatmap.png
#
# Environment:
#   AUTHOR_COL (default: label_author)
#   EXTERNAL_COL (default: label_external)
#   OUT_TXT (default: same dir as csv)/kappa_summary.txt

CSV_PATH="${1:-}"
OUT_FIG="${2:-}"

if [[ -z "$CSV_PATH" || -z "$OUT_FIG" ]]; then
  echo "Usage: $0 <coding_labels_wide.csv> <out_heatmap.png>"
  exit 1
fi

AUTHOR_COL=${AUTHOR_COL:-label_author}
EXTERNAL_COL=${EXTERNAL_COL:-label_external}

CSV_DIR="$(cd "$(dirname "$CSV_PATH")" && pwd)"
OUT_TXT="${OUT_TXT:-$CSV_DIR/kappa_summary.txt}"

# 1) Kappa
python scripts/calc_kappa_external_coder.py \
  --author-col "$AUTHOR_COL" \
  --external-col "$EXTERNAL_COL" \
  "$CSV_PATH" | tee "$OUT_TXT"

# 2) Heatmap (case × indicator disagreement rate)
python scripts/render_disagreement_heatmap.py \
  "$CSV_PATH" \
  --author-col "$AUTHOR_COL" \
  --external-col "$EXTERNAL_COL" \
  --out-fig "$OUT_FIG"

echo "[build_kappa_and_heatmap] Done. Summary: $OUT_TXT, Heatmap: $OUT_FIG"
