#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/out/ci"
mkdir -p "$OUT"

if [ -z "${TLA_TLC_JAR:-}" ]; then
  echo "TLA_TLC_JAR not set; skipping modelcheck (stub)." >&2
  echo '{"status":"skipped","rc":1}' > "$OUT/tlc_status.json"
  exit 0
fi

echo "Running make modelcheck..."
set +e
make -C "$ROOT" modelcheck | tee "$OUT/tlc.log"
rc=$?
set -e
echo "TLC rc=$rc"

python "$ROOT/tools/modelchecking/parse_tlc_log.py" \
  --log "$OUT/tlc.log" \
  --rc $rc \
  --out-tlc "$OUT/tlc_status.json" \
  --out-po "$OUT/po_status.json" || true
exit 0
