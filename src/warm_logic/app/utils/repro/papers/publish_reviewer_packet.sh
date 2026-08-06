#!/usr/bin/env bash
set -euo pipefail

# Publish a reviewer packet for Paper 5 to releases/reviewer_packets
# Usage: scripts/papers/publish_reviewer_packet.sh [--date YYYYMMDD] [--venue <slug>]

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

# Ensure latest artifacts
bash "$SUBDIR/export_figs_pdf.sh"
bash "$SUBDIR/build_pdf.sh"
bash "$SUBDIR/build_responses_pdf.sh"

DEST_BASE="$ROOT/docs/papers/releases/reviewer_packets"
mkdir -p "$DEST_BASE"

PKT_DIR="Paper5_Reviewer_Packet_${DATE}"
TMPDIR="$(mktemp -d)"; trap 'rm -rf "$TMPDIR"' EXIT
OUT_ZIP="$DEST_BASE/${PKT_DIR}.zip"

mkdir -p "$TMPDIR/$PKT_DIR/paper" "$TMPDIR/$PKT_DIR/figures" "$TMPDIR/$PKT_DIR/responses" "$TMPDIR/$PKT_DIR/covers"

# Copy paper, figures, responses (with metadata scrub if available)
SCRUB="$ROOT/scripts/papers/scrub_pdf_metadata.sh"
copy_pdf() {
  local src="$1" dst="$2"
  if [[ -x "$SCRUB" && -f "$src" ]]; then
    bash "$SCRUB" "$src" "$dst"
  else
    cp -f "$src" "$dst"
  fi
}

copy_pdf "$SUBDIR/Paper5_StressTest_Reopenability.pdf" "$TMPDIR/$PKT_DIR/paper/Paper5_StressTest_Reopenability.pdf"
cp -f "$SUBDIR/response_facct.md" "$TMPDIR/$PKT_DIR/responses/" || true
cp -f "$SUBDIR/response_ethics_it.md" "$TMPDIR/$PKT_DIR/responses/" || true
copy_pdf "$SUBDIR/response_facct.pdf" "$TMPDIR/$PKT_DIR/responses/response_facct.pdf" || true
copy_pdf "$SUBDIR/response_ethics_it.pdf" "$TMPDIR/$PKT_DIR/responses/response_ethics_it.pdf" || true
cp -f "$SUBDIR/cover_facct.md" "$TMPDIR/$PKT_DIR/covers/" || true
cp -f "$SUBDIR/cover_ethics_it.md" "$TMPDIR/$PKT_DIR/covers/" || true
copy_pdf "$SUBDIR/cover_facct.pdf" "$TMPDIR/$PKT_DIR/covers/cover_facct.pdf" || true
copy_pdf "$SUBDIR/cover_ethics_it.pdf" "$TMPDIR/$PKT_DIR/covers/cover_ethics_it.pdf" || true

shopt -s nullglob
for f in "$FIGDIR"/*.pdf; do cp -f "$f" "$TMPDIR/$PKT_DIR/figures/"; done

(cd "$TMPDIR" && zip -r "$OUT_ZIP" "$PKT_DIR" >/dev/null)
ln -sfn "$(basename "$OUT_ZIP")" "$DEST_BASE/Paper5_Reviewer_Packet_latest.zip"
if [[ -n "$VENUE" ]]; then
  ln -sfn "$(basename "$OUT_ZIP")" "$DEST_BASE/Paper5_Reviewer_Packet_latest_${VENUE}.zip"
fi

echo "[publish-reviewer] -> $OUT_ZIP"
