#!/usr/bin/env bash
set -euo pipefail

# Package Paper 5 camera-ready figures (Figure 2 + Appendix B mini-tables) into a zip.

DATE="$(date +%Y%m%d)"
VENUE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --date) DATE="$2"; shift 2;;
    --venue) VENUE="$2"; shift 2;;
    -h|--help) echo "Usage: $0 [--date YYYYMMDD]"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
P5_ROOT="$ROOT/docs/papers/ai_ethics/2026_stress_test_reopenability"
SUBDIR="$P5_ROOT/submission"
FIGDIR="$P5_ROOT/figures"

# Ensure figure 2 export and build mini-table PDFs
bash "$SUBDIR/export_figs_pdf.sh"
bash "$SUBDIR/build_tables_pdf.sh"

DEST_BASE="$ROOT/docs/papers/releases/figures"
mkdir -p "$DEST_BASE"

PKT_DIR="Paper5_Figures_${DATE}"
TMPDIR="$(mktemp -d)"; trap 'rm -rf "$TMPDIR"' EXIT
OUT_ZIP="$DEST_BASE/${PKT_DIR}.zip"

mkdir -p "$TMPDIR/$PKT_DIR/figures"

# Copy figure 2 and appendix table PDFs
cp -f "$FIGDIR/fig_pass_pipeline.pdf" "$TMPDIR/$PKT_DIR/figures/" || true
cp -f "$FIGDIR/appendix_b_case_a_rule_only.pdf" "$TMPDIR/$PKT_DIR/figures/" || true
cp -f "$FIGDIR/appendix_b_case_b_rule_only.pdf" "$TMPDIR/$PKT_DIR/figures/" || true
cp -f "$FIGDIR/appendix_b_comparative_summary.pdf" "$TMPDIR/$PKT_DIR/figures/" || true

# Captions (camera-ready)
CAPT="$TMPDIR/$PKT_DIR/captions.md"
cat > "$CAPT" <<'EOF'
# Paper 5 — Camera‑Ready Figure Captions

Figure 2 — Indicator → Rule → Diagnosis (Non‑Compensatory PASS Logic).
Indicators are observed and mapped to explicit decision rules. Diagnosis is non‑compensatory: any single FAIL collapses reopenability, regardless of other satisfied indicators. This design prevents aggregation, gaming, and discretionary closure by enforcing necessary‑condition evaluation prior to judgment. The contrasted cases in Appendix B show why scoring‑based assessments misclassify structurally closed systems as acceptable.

Appendix B — Rule‑Only Diagnosis (Case A — PASS/PASS).
All necessary conditions satisfied (Authority, Evidence, Time, Reversal, Cost) → PASS. No scoring required — binary rules suffice.

Appendix B — Rule‑Only Diagnosis (Case B — PASS/FAIL).
Single‑path collapse across Authority, Evidence, Reversal, and Cost yields overall FAIL; partial strength elsewhere cannot compensate (non‑compensatory).

Appendix B — Comparative Summary.
Score‑based maturity can overrate structurally closed systems. PASS detects the non‑compensatory condition: one blocked pathway closes the system.
EOF

(cd "$TMPDIR" && zip -r "$OUT_ZIP" "$PKT_DIR" >/dev/null)
ln -sfn "$(basename "$OUT_ZIP")" "$DEST_BASE/Paper5_Figures_latest.zip"
if [[ -n "$VENUE" ]]; then
  ln -sfn "$(basename "$OUT_ZIP")" "$DEST_BASE/Paper5_Figures_latest_${VENUE}.zip"
  # Venue subfolder links (figures/<venue>/latest_p5.zip)
  mkdir -p "$DEST_BASE/$VENUE"
  ln -sfn "../$(basename "$OUT_ZIP")" "$DEST_BASE/$VENUE/latest_p5.zip"
fi

echo "[publish-figs] -> $OUT_ZIP"
