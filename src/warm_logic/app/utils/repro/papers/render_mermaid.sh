#!/usr/bin/env bash
set -euo pipefail

# Render Mermaid diagrams to SVG/PDF if mermaid-cli (mmdc) is available.
# Falls back to warnings if mmdc is missing.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FIG_DIR="$ROOT/docs/papers/ai_ethics/2026_stress_test_reopenability/figures"

IN_MMD="$FIG_DIR/fig2_indicator_rule_diagnosis.mmd"
OUT_SVG="$FIG_DIR/fig_pass_pipeline.svg"

if [[ ! -f "$IN_MMD" ]]; then
  echo "[mermaid] Input not found: $IN_MMD" >&2
  exit 1
fi

if ! command -v mmdc >/dev/null 2>&1; then
  echo "[mermaid] 'mmdc' not found. Skipping Mermaid render; using existing SVG if present: $OUT_SVG" >&2
  exit 0
fi

echo "[mermaid] Rendering $IN_MMD → $OUT_SVG"
mmdc -i "$IN_MMD" -o "$OUT_SVG" --backgroundColor "#ffffff" --width 980 --height 360
echo "[mermaid] Done"
