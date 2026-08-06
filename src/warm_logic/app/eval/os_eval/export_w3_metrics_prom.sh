#!/usr/bin/env bash
set -euo pipefail

# Export W3 metrics from Prometheus into metrics/metrics.json for a given run.
# Usage:
#   PROM=http://127.0.0.1:39090 \
#   scripts/os_eval/export_w3_metrics_prom.sh \
#     --namespace policy-logging \
#     --run-id W3_..._POLICYLOG \
#     --mode policylog
#
# Notes:
# - Latency/throughput are taken from app metrics when available:
#     policylog_* for Policy+Logging, osv2_* for OS v2.
# - Resource metrics use cadvisor (container_cpu_usage_seconds_total, etc.) scoped by namespace.
# - Missing series are left unchanged.

PROM=${PROM:-http://127.0.0.1:39090}
NAMESPACE=""
RUN_ID=""
MODE=""
RUN_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace) NAMESPACE="$2"; shift 2;;
    --run-id) RUN_ID="$2"; shift 2;;
    --mode) MODE="$2"; shift 2;;
    --run-root) RUN_ROOT="$2"; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 1;;
  esac
done

if [[ -z "$RUN_ID" || -z "$MODE" ]]; then
  echo "Usage: PROM=<url> $0 --run-id <id> --mode <osv2|policylog|temporal> [--namespace <ns>] [--run-root <dir>]" >&2
  exit 1
fi

if [[ -z "$RUN_ROOT" ]]; then
  RUN_ROOT="artifacts/os_v2/longhaul/${RUN_ID}"
fi

OUT_ROOT="${RUN_ROOT%/}/metrics"
MET_FILE="${OUT_ROOT}/metrics.json"
PROMQL_DUMP="${OUT_ROOT}/promql_dump.json"
if [[ ! -f "$MET_FILE" ]]; then
  echo "Missing metrics file: ${MET_FILE}" >&2
  exit 1
fi

mkdir -p "$OUT_ROOT"

fetch() {
  local q="$1"
  curl -sG "${PROM}/api/v1/query" --data-urlencode "query=$q" \
    | jq -r '.data.result[0].value[1] // empty'
}

fetch_json() {
  local q="$1"
  curl -sG "${PROM}/api/v1/query" --data-urlencode "query=$q"
}

ns_labels() {
  # Returns: ',namespace="...'" or empty string.
  if [[ -n "${NAMESPACE:-}" ]]; then
    echo ",namespace=\"${NAMESPACE}\""
  else
    echo ""
  fi
}

# Select app metric prefixes
case "$MODE" in
  policylog)
    W3_PATH_RE='^/(handoff/(transfer|ack)|operate|rollback)$'
    APP_SEL='method="POST",path=~"'$W3_PATH_RE'"'"$(ns_labels)"''
    LAT_Q99='histogram_quantile(0.99, sum(rate(policylog_request_duration_seconds_bucket{'$APP_SEL'}[5m])) by (le))'
    LAT_Q95='histogram_quantile(0.95, sum(rate(policylog_request_duration_seconds_bucket{'$APP_SEL'}[5m])) by (le))'
    THROUGHPUT='sum(rate(policylog_requests_total{'$APP_SEL'}[5m]))'
    ;;
  osv2)
    W3_PATH_RE='^/(handoff/(transfer|ack)|operate|rollback)$'
    APP_SEL='path=~"'$W3_PATH_RE'"'"$(ns_labels)"''
    LAT_Q99='histogram_quantile(0.99, sum(rate(osv2_request_duration_seconds_bucket{'$APP_SEL'}[5m])) by (le))'
    LAT_Q95='histogram_quantile(0.95, sum(rate(osv2_request_duration_seconds_bucket{'$APP_SEL'}[5m])) by (le))'
    THROUGHPUT='sum(rate(osv2_requests_total{'$APP_SEL'}[5m]))'
    ;;
  temporal)
    # No app-level metrics today; leave latency/throughput unchanged
    LAT_Q99=""
    LAT_Q95=""
    THROUGHPUT=""
    ;;
  *)
    LAT_Q99=""
    LAT_Q95=""
    THROUGHPUT=""
    ;;
esac

CPU=""
MEM=""
NET=""
STO=""
if [[ -n "${NAMESPACE:-}" ]]; then
  CPU='sum(rate(container_cpu_usage_seconds_total{namespace="'$NAMESPACE'"}[5m]))'
  MEM='sum(container_memory_working_set_bytes{namespace="'$NAMESPACE'"})'
  NET='sum(rate(container_network_transmit_bytes_total{namespace="'$NAMESPACE'"}[5m])) + sum(rate(container_network_receive_bytes_total{namespace="'$NAMESPACE'"}[5m]))'
  STO='sum(container_fs_usage_bytes{namespace="'$NAMESPACE'"}[5m])'
fi

P99=$( [[ -n "$LAT_Q99" ]] && fetch "$LAT_Q99" || echo "" )
P95=$( [[ -n "$LAT_Q95" ]] && fetch "$LAT_Q95" || echo "" )
TPUT=$( [[ -n "$THROUGHPUT" ]] && fetch "$THROUGHPUT" || echo "" )
CPU_V=$( [[ -n "$CPU" ]] && fetch "$CPU" || echo "" )
MEM_V=$( [[ -n "$MEM" ]] && fetch "$MEM" || echo "" )
NET_V=$( [[ -n "$NET" ]] && fetch "$NET" || echo "" )
STO_V=$( [[ -n "$STO" ]] && fetch "$STO" || echo "" )

# Record PromQL provenance when queries exist.
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

write_q() {
  local key="$1"
  local q="$2"
  if [[ -z "$q" ]]; then
    return
  fi
  printf "%s" "$q" > "${tmpdir}/${key}.query"
  fetch_json "$q" > "${tmpdir}/${key}.json"
}

write_q "lat_q95" "$LAT_Q95"
write_q "lat_q99" "$LAT_Q99"
write_q "throughput" "$THROUGHPUT"
write_q "cpu" "$CPU"
write_q "mem" "$MEM"
write_q "net" "$NET"
write_q "sto" "$STO"

TMPDIR_W3_PROMQL="$tmpdir" \
OUT_W3_PROMQL="$PROMQL_DUMP" \
RUN_ID_W3_PROMQL="$RUN_ID" \
MODE_W3_PROMQL="$MODE" \
PROM_W3_PROMQL="$PROM" \
NAMESPACE_W3_PROMQL="${NAMESPACE:-}" \
python - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

tmpdir = Path(os.environ["TMPDIR_W3_PROMQL"])
out_path = Path(os.environ["OUT_W3_PROMQL"])
meta = {
    "run_id": os.environ["RUN_ID_W3_PROMQL"],
    "mode": os.environ["MODE_W3_PROMQL"],
    "prom_base": os.environ["PROM_W3_PROMQL"],
    "namespace": os.environ.get("NAMESPACE_W3_PROMQL") or None,
    "collected_at": datetime.now(timezone.utc).isoformat(),
    "queries": {},
}

for query_path in sorted(tmpdir.glob("*.query")):
    key = query_path.stem
    q = query_path.read_text(encoding="utf-8")
    resp_path = tmpdir / f"{key}.json"
    resp = json.loads(resp_path.read_text(encoding="utf-8")) if resp_path.exists() else None
    meta["queries"][key] = {"query": q, "response": resp}

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
PY


tmp="$(mktemp)"
jq \
  --arg p95 "$P95" --arg p99 "$P99" --arg t "$TPUT" \
  --arg cpu "$CPU_V" --arg mem "$MEM_V" --arg net "$NET_V" --arg sto "$STO_V" \
  '
  if ($p95 != "") then .p95_ms=($p95|tonumber*1000) else . end |
  if ($p99 != "") then .p99_ms=($p99|tonumber*1000) else . end |
  if ($t   != "") then .throughput_rps=($t|tonumber) else . end |
  if ($cpu != "") then .cpu_pct=($cpu|tonumber*100) else . end |
  if ($mem != "") then .mem_mb=($mem|tonumber/1024/1024) else . end |
  if ($net != "") then .net_mbps=($net|tonumber/1024/1024*8) else . end |
  if ($sto != "") then .storage_gb=($sto|tonumber/1024/1024/1024) else . end
  ' "$MET_FILE" > "$tmp"
mv "$tmp" "$MET_FILE"

sha256_files() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256
    return
  fi
  echo "No sha256 tool found (need sha256sum or shasum)" >&2
  return 1
}

(
  cd "$(dirname "$RUN_ROOT")"
  find "$(basename "$RUN_ROOT")" -type f -print0 | sort -z | xargs -0 sha256_files
) > "${OUT_ROOT%/metrics}/MANIFEST.sha256"

echo "[ok] Updated metrics.json from Prometheus for ${RUN_ID} (namespace=${NAMESPACE:-<none>}, mode=${MODE})"
echo "[ok] Wrote PromQL provenance: ${PROMQL_DUMP}"
