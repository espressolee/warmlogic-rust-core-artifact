#!/usr/bin/env bash
set -euo pipefail

# Build PDFs for Papers 1–6 (ai_ethics series) in one go.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

SCRIPTS=(
  "${ROOT}/docs/papers/ai_ethics/2025_beyond_the_ubermensch/submission/build_pdf.sh"
  "${ROOT}/docs/papers/ai_ethics/2026_moral_finality_measurement_kit/submission/build_pdf.sh"
  "${ROOT}/docs/papers/ai_ethics/2026_case_anatomy_internal_ethics/submission/build_pdf.sh"
  "${ROOT}/docs/papers/ai_ethics/2026_intervention_design_reopenability/submission/build_pdf.sh"
  "${ROOT}/docs/papers/ai_ethics/2026_stress_test_reopenability/submission/build_pdf.sh"
  "${ROOT}/docs/papers/ai_ethics/2026_adversarial_closure/submission/build_pdf.sh"
)

if ! command -v pandoc >/dev/null 2>&1; then
  echo "[ERROR] pandoc not found. Install pandoc (e.g., brew install pandoc)." >&2
  exit 1
fi

# Warn if no SVG converter is present (needed for .svg figures)
if ! command -v rsvg-convert >/dev/null 2>&1 && ! command -v inkscape >/dev/null 2>&1; then
  echo "[warn] Neither rsvg-convert nor inkscape found; SVG embedding may fail." >&2
  echo "       Install one of: brew install librsvg   or   brew install --cask inkscape" >&2
fi

STATUS=0
for s in "${SCRIPTS[@]}"; do
  if [[ -f "$s" ]]; then
    echo "[build-all] Running: $s"
    if ! bash "$s"; then
      echo "[build-all] Failed: $s" >&2
      STATUS=1
    fi
  else
    echo "[build-all] Missing script: $s" >&2
    STATUS=1
  fi
done

if [[ $STATUS -eq 0 ]]; then
  echo "[build-all] Success: all PDFs built."
else
  echo "[build-all] Completed with errors. See logs above." >&2
fi

exit $STATUS
