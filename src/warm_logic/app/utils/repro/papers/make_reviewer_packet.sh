#!/usr/bin/env bash
set -euo pipefail

OUT_DIR=${1:-docs/papers/out/reviewer_packets}
mkdir -p "$OUT_DIR"

PACK_MD="$OUT_DIR/Reviewer_Packet.md"
PACK_PDF="$OUT_DIR/Reviewer_Packet.pdf"

echo "# Reviewer Packet — Moral Finality & Reopenability" > "$PACK_MD"
echo >> "$PACK_MD"
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$PACK_MD"
echo >> "$PACK_MD"

# Include 1-pager conclusion and pointers to core chapters
if [ -f docs/papers/ai_ethics/phd/Conclusion_1pager.md ]; then
  echo "\n---\n" >> "$PACK_MD"
  echo "## Conclusion — 1‑Page Summary" >> "$PACK_MD"
  echo >> "$PACK_MD"
  cat docs/papers/ai_ethics/phd/Conclusion_1pager.md >> "$PACK_MD"
fi

echo "\n---\n" >> "$PACK_MD"
echo "## Chapter Pointers" >> "$PACK_MD"
echo "- Constraints (Chapter Y): docs/papers/ai_ethics/phd/Chapter_Y_Design_Constraints.md" >> "$PACK_MD"
echo "- Indicators (Chapter Z): docs/papers/ai_ethics/phd/Chapter_Z_Indicators.md" >> "$PACK_MD"
echo "- Comparative Evaluation (Chapter W): docs/papers/ai_ethics/phd/Chapter_W_Comparative_Evaluation.md" >> "$PACK_MD"

# Try to build PDF if pandoc is available
if command -v pandoc >/dev/null 2>&1; then
  pandoc "$PACK_MD" -o "$PACK_PDF" || true
  echo "[reviewer-packet] Wrote $PACK_MD and (if pandoc available) $PACK_PDF"
else
  echo "[reviewer-packet] Wrote $PACK_MD (pandoc not found; skipping PDF)"
fi
