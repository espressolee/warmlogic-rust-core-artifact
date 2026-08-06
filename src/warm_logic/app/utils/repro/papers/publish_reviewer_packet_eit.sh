#!/usr/bin/env bash
set -euo pipefail

# Publish an E&IT-specific reviewer packet for Paper 5:
# paper PDF + appendices PDFs + E&IT cover letter, no extra figures/responses.
# Usage: scripts/papers/publish_reviewer_packet_eit.sh [--date YYYYMMDD]

DATE="$(date +%Y%m%d)"
VENUE="ethics_it"
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

# Ensure latest artifacts
bash "$SUBDIR/build_pdf.sh"
bash "$SUBDIR/build_responses_pdf.sh"

#############################
# Sources (paper + appendices + cover + responses)
PAPER_PDF="$SUBDIR/Paper5_StressTest_Reopenability.pdf"
COVER_EIT_PDF="$SUBDIR/cover_ethics_it.pdf"
APP_A_PDF="$SUBDIR/appendix_a_indicator_mapping.pdf"
APP_B_PDF="$SUBDIR/appendix_b_worked_examples.pdf"
RESP_EIT_PDF="$SUBDIR/response_ethics_it.pdf"
RESP_FACCT_PDF="$SUBDIR/response_facct.pdf"

for f in "$PAPER_PDF" "$COVER_EIT_PDF" "$APP_A_PDF" "$APP_B_PDF" "$RESP_EIT_PDF"; do
  [[ -f "$f" ]] || { echo "[EIT-packet] missing: $f" >&2; exit 1; }
done

DEST_BASE="$ROOT/docs/papers/releases/reviewer_packets"
mkdir -p "$DEST_BASE"

PKT_DIR="Paper5_EandIT_Reviewer_Packet_${DATE}"
TMPDIR="$(mktemp -d)"; trap 'rm -rf "$TMPDIR"' EXIT
OUT_ZIP="$DEST_BASE/${PKT_DIR}.zip"

mkdir -p "$TMPDIR/$PKT_DIR/paper" "$TMPDIR/$PKT_DIR/appendices" "$TMPDIR/$PKT_DIR/cover" "$TMPDIR/$PKT_DIR/responses"

# Scrub metadata and copy
SCRUB="$ROOT/scripts/papers/scrub_pdf_metadata.sh"
if [[ -x "$SCRUB" ]]; then
  bash "$SCRUB" "$PAPER_PDF" "$TMPDIR/$PKT_DIR/paper/Paper5_StressTest_Reopenability.pdf"
  bash "$SCRUB" "$APP_A_PDF" "$TMPDIR/$PKT_DIR/appendices/appendix_a_indicator_mapping.pdf"
  bash "$SCRUB" "$APP_B_PDF" "$TMPDIR/$PKT_DIR/appendices/appendix_b_worked_examples.pdf"
  bash "$SCRUB" "$COVER_EIT_PDF" "$TMPDIR/$PKT_DIR/cover/cover_ethics_it.pdf"
  bash "$SCRUB" "$RESP_EIT_PDF" "$TMPDIR/$PKT_DIR/responses/response_ethics_it.pdf"
  if [[ -f "$RESP_FACCT_PDF" ]]; then
    bash "$SCRUB" "$RESP_FACCT_PDF" "$TMPDIR/$PKT_DIR/responses/response_facct.pdf"
  fi
else
  cp -f "$PAPER_PDF" "$TMPDIR/$PKT_DIR/paper/"
  cp -f "$APP_A_PDF" "$APP_B_PDF" "$TMPDIR/$PKT_DIR/appendices/"
  cp -f "$COVER_EIT_PDF" "$TMPDIR/$PKT_DIR/cover/"
  cp -f "$RESP_EIT_PDF" "$TMPDIR/$PKT_DIR/responses/"
  [[ -f "$RESP_FACCT_PDF" ]] && cp -f "$RESP_FACCT_PDF" "$TMPDIR/$PKT_DIR/responses/"
fi

# Write per-packet checksums
(
  cd "$TMPDIR/$PKT_DIR"
  DEST="CHECKSUMS_SHA256.txt"
  : > "$DEST"
  gen_hash() {
    local f="$1"
    if command -v sha256sum >/dev/null 2>&1; then
      sha256sum "$f" >> "$DEST"
    else
      shasum -a 256 "$f" >> "$DEST"
    fi
  }
  for f in \
    paper/Paper5_StressTest_Reopenability.pdf \
    appendices/appendix_a_indicator_mapping.pdf \
    appendices/appendix_b_worked_examples.pdf \
    cover/cover_ethics_it.pdf \
    responses/response_ethics_it.pdf \
    responses/response_facct.pdf; do
    [[ -f "$f" ]] && gen_hash "$f"
  done
)

(cd "$TMPDIR" && zip -r "$OUT_ZIP" "$PKT_DIR" >/dev/null)
ln -sfn "$(basename "$OUT_ZIP")" "$DEST_BASE/Paper5_EandIT_Reviewer_Packet_latest.zip"
ln -sfn "$(basename "$OUT_ZIP")" "$DEST_BASE/Paper5_EandIT_Reviewer_Packet_latest_${VENUE}.zip"

echo "[EIT-packet] -> $OUT_ZIP"
