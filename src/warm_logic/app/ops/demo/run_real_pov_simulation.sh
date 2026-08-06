#!/usr/bin/env bash
# run_real_pov_simulation.sh — Simulate First Real PoV (Corp-A)
# End-to-end simulation of a client PoV engagement

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS=$(date -u +%Y%m%dT%H%M%SZ)

POV_CLIENT="PoV-Corp-A"
POV_DIR="$ROOT/out/p_runs/POV_CORP_A_${TS}"

echo "=============================================="
echo " Simulating First Real PoV: $POV_CLIENT"
echo "=============================================="
mkdir -p "$POV_DIR"

# 1. Installation Phase
echo "[1/4] Installing PoV Kit..."
# Simulate config generation
cat > "$POV_DIR/client_config.yaml" <<EOF
org_id: "corp-a"
env: "prod-shadow"
veto_policy: "strict"
EOF

# 2. Execution Phase (Success Run)
echo "[2/4] Executing Workflow (Run 1: Approved Limit Change)..."
cat > "$POV_DIR/run_manifest_success.json" <<EOF
{
  "run_id": "POV_A_RUN_001",
  "client": "corp-a",
  "action": "update_limit",
  "witness": "approver_sig_valid",
  "result": "allowed"
}
EOF

# 3. Execution Phase (Blocked Run)
echo "[3/4] Executing Workflow (Run 2: Unapproved Action)..."
cat > "$POV_DIR/run_manifest_blocked.json" <<EOF
{
  "run_id": "POV_A_RUN_002",
  "client": "corp-a",
  "action": "emergency_shutdown",
  "witness": null,
  "result": "denied"
}
EOF
# Generate CE
cat > "$POV_DIR/Counterexamples_v1.json" <<EOF
[{
  "counterexample_id": "CE-POV-A-${TS}",
  "kind": "CE_SHUTDOWN_DENIED_MISSING_COO_SIG",
  "run_id": "POV_A_RUN_002",
  "reason": "Emergency shutdown requires COO signature",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}]
EOF

# 4. Deliverable Generation
echo "[4/4] Generating Evidence Pack & Report..."
bash "$ROOT/scripts/audit/build_evidence_pack_v1.sh" --run-dir "$POV_DIR" --out-dir "$POV_DIR/final_deliverable" >/dev/null 2>&1

# PoV Report
cat > "$POV_DIR/PoV_Closure_Report.md" <<EOF
# PoV Closure Report: $POV_CLIENT

## Summary
- **Duration**: 2 weeks
- **Total Runs**: 2
- **Blocked**: 1 (Critical Safety Catch)

## Key Value
WarmLogic successfully blocked an unauthorized emergency shutdown attempt (Run 002), providing a counterexample: \`CE_SHUTDOWN_DENIED_MISSING_COO_SIG\`.

## Recommendation
Proceed to full implementation for 'Core Infrastructure' scope.
EOF

echo "=============================================="
echo " PoV Simulation Complete -> $POV_DIR"
echo "=============================================="
