#!/usr/bin/env bash
# Generate dashboard-ready safety artifacts from existing outputs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT_DIR/out"

TLC_LOG="$OUT_DIR/modelchecking/tlc.log"
TLC_RC="${TLC_RC:-0}"

if [[ -f "$TLC_LOG" ]]; then
  python "$ROOT_DIR/tools/modelchecking/parse_tlc_log.py" \
    --log "$TLC_LOG" \
    --rc "$TLC_RC"
fi

# Build dashboard SafetySnapshot (best-effort; does not fail pipeline)
python - <<'PY'
from pathlib import Path

from warm_logic.monitor.safety_snapshot_builder import build_snapshot_from_out_dir

root = Path(__file__).resolve().parents[1].parent
try:
    build_snapshot_from_out_dir(root / "out", write_to=root / "out" / "dashboard" / "safety_snapshot.json")
except Exception:
    pass
PY

echo "Safety artifacts emitted under $OUT_DIR/dashboard and $OUT_DIR/modelchecking"
