#!/usr/bin/env bash
set -euo pipefail

# Package Paper 6 camera-ready figures (PDFs) + captions into a zip.

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
P6_ROOT="$ROOT/docs/papers/ai_ethics/2026_adversarial_closure"
SUBDIR="$P6_ROOT/submission"
FIGDIR="$P6_ROOT/figures"

# Ensure figures are exported
bash "$SUBDIR/export_figs_pdf.sh"
bash "$SUBDIR/build_tables_pdf.sh"

DEST_BASE="$ROOT/docs/papers/releases/figures"
mkdir -p "$DEST_BASE"

PKT_DIR="Paper6_Figures_${DATE}"
TMPDIR="$(mktemp -d)"; trap 'rm -rf "$TMPDIR"' EXIT
OUT_ZIP="$DEST_BASE/${PKT_DIR}.zip"

mkdir -p "$TMPDIR/$PKT_DIR/figures"

# Copy figure PDFs
cp -f "$FIGDIR/fig_boundary_failure_map.pdf" "$TMPDIR/$PKT_DIR/figures/" || true
cp -f "$FIGDIR/fig_pass_survival.pdf" "$TMPDIR/$PKT_DIR/figures/" || true
cp -f "$FIGDIR/fig_fail_cascade.pdf" "$TMPDIR/$PKT_DIR/figures/" || true
cp -f "$FIGDIR/fig_federation_dampers_timeline.pdf" "$TMPDIR/$PKT_DIR/figures/" || true
cp -f "$FIGDIR/appendix_a_comparative_stress_table.pdf" "$TMPDIR/$PKT_DIR/figures/" || true

# Captions (camera-ready)
CAPT="$TMPDIR/$PKT_DIR/captions.md"
cat > "$CAPT" <<'EOF'
# Paper 6 — Camera‑Ready Figure Captions

Figure 5 — Federation PASS Collapse and Recovery via Dampers.
Federated dampers (AD/LBP/RE) preserve reopenability under authority dispersion by enforcing necessary conditions. Authority Dispersion (AD), Latency‑Bounded Process (LBP), and Reversal Economics (RE) prevent composition‑driven closure; if any condition is absent, the diagnosis returns FAIL without compensation.

Figure 2 — Boundary Failure Map (Aᵦ / Eₚ / R𝚌).
Map of cross‑organizational interfaces showing how Authority, Evidence, and Reversal pathways either preserve reopenability (✓) or collapse at the boundary (×). Diagnosis is non‑compensatory: any single blocked pathway across a boundary yields FAIL, even when others appear intact.

Figure 3 — PASS Invariants Across Governance Regimes.
Each cell indicates whether the invariant is preserved (●), fragile (○), or collapsed (×) as authority shifts from internal decision to external scrutiny. Diagnosis is non‑compensatory: external PASS requires all invariants (A*, E*, T*, R*, C*); any single collapse yields FAIL.

Figure 4 — FAIL Cascade under Partial PASS (Authority‑Only Survival).
Preserving procedural authority while restricting evidence and blocking reversal produces a non‑compensatory failure cascade: authority decays into symbolic approval, decisions close, and reversal costs transform ethics into a responsibility sink rather than a corrective mechanism.

Appendix A — Comparative Stress Table.
Frameworks vs. stress sensitivity across Authority, Evidence, Time, Reversal, Cost. PASS uniquely detects single‑path closure (non‑compensatory); prevailing frameworks produce false negatives under stress by evaluating presence over reopenability.
EOF

(cd "$TMPDIR" && zip -r "$OUT_ZIP" "$PKT_DIR" >/dev/null)
ln -sfn "$(basename "$OUT_ZIP")" "$DEST_BASE/Paper6_Figures_latest.zip"
if [[ -n "$VENUE" ]]; then
  ln -sfn "$(basename "$OUT_ZIP")" "$DEST_BASE/Paper6_Figures_latest_${VENUE}.zip"
  # Venue subfolder links (figures/<venue>/latest_p6.zip)
  mkdir -p "$DEST_BASE/$VENUE"
  ln -sfn "../$(basename "$OUT_ZIP")" "$DEST_BASE/$VENUE/latest_p6.zip"
fi

echo "[publish-figs] -> $OUT_ZIP"
