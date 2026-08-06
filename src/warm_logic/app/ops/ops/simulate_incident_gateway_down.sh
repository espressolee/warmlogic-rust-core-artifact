#!/usr/bin/env bash
# simulate_incident_gateway_down.sh — Simulate Gateway Down Incident
# SEV-1 Simulation: Gateway returns 500 or timeout

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS=$(date -u +%Y%m%dT%H%M%SZ)
INCIDENT_ID="INCIDENT_SIM_GATEWAY_DOWN_${TS}"
OUT_DIR="$ROOT/out/incidents/$INCIDENT_ID"

echo "=============================================="
echo " Incident Simulation: Gateway Down (SEV-1)"
echo "=============================================="
mkdir -p "$OUT_DIR"

# 1. Trigger Incident (Simulated)
echo "[1/3] Triggering simulated failure..."
# In a real system, we'd inject fault. Here we just log the start.
echo "timestamp: $TS" > "$OUT_DIR/trigger.log"
echo "type: gateway_timeout" >> "$OUT_DIR/trigger.log"

# 2. Response: Enable Fail-Open (Simulation)
echo "[2/3] Simulating automated response (Fail-Open)..."
FAIL_OPEN_CE_ID="CE-FAIL-OPEN-${TS}"
cat > "$OUT_DIR/ce_ledger_update.json" <<EOF
{
  "counterexample_id": "$FAIL_OPEN_CE_ID",
  "kind": "CE_FAIL_OPEN_EMERGENCY",
  "reason": "Gateway timeout > 30s",
  "incident_id": "$INCIDENT_ID",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# 3. Post-Mortem Artifacts
echo "[3/3] Generating post-mortem artifacts..."
cat > "$OUT_DIR/monitor_log.json" <<EOF
{
  "incident_id": "$INCIDENT_ID",
  "duration_sec": 45,
  "requests_fail_opened": 120,
  "recovery_ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "=============================================="
echo " Simulation Complete -> $OUT_DIR"
echo "=============================================="
