#!/usr/bin/env bash
# run_client_simulations.sh — Simulate Client-1/2 runs and build Evidence Packs
# Generates synthetic evidence for Finance and Moderation scenarios

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS=$(date -u +%Y%m%dT%H%M%SZ)

echo "=============================================="
echo " Running Client Scenarios (Simulation)"
echo "=============================================="

# -----------------------------------------------------------------------------
# Client-1: Finance (Limit Change)
# -----------------------------------------------------------------------------
echo ">> Client-1: Finance..."
C1_RUN_ID="RUN_CLIENT1_FINANCE_${TS}"
C1_DIR="$ROOT/out/p_runs/$C1_RUN_ID"
mkdir -p "$C1_DIR"

# 1. Success Run
echo "   - Simulating Success (Limit Increase w/ Approval)"
SUCCESS_DIR="$C1_DIR/success"
mkdir -p "$SUCCESS_DIR"
cat > "$SUCCESS_DIR/run_manifest.json" <<EOF
{
  "run_id": "${C1_RUN_ID}_SUCCESS",
  "client": "client-1-finance",
  "scenario": "limit_change",
  "result": "allowed",
  "evidence": "manager_approval_signed.json",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
# Dummy veto decision
cat > "$SUCCESS_DIR/veto_decision.json" <<EOF
{
  "schema_version": "veto_decision_v1",
  "allow": true,
  "request_sha256": "dummy_hash_success",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# 2. Failure Run
echo "   - Simulating Failure (Limit Increase w/o Approval)"
FAILURE_DIR="$C1_DIR/failure"
mkdir -p "$FAILURE_DIR"
cat > "$FAILURE_DIR/run_manifest.json" <<EOF
{
  "run_id": "${C1_RUN_ID}_FAILURE",
  "client": "client-1-finance",
  "scenario": "limit_change",
  "result": "denied",
  "evidence": null,
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
# Dummy CE
cat > "$FAILURE_DIR/Counterexamples_v1.json" <<EOF
[{
  "counterexample_id": "CE-LIMIT-CHANGE-DENIED-${TS}",
  "kind": "CE_LIMIT_CHANGE_DENIED_MISSING_APPROVAL",
  "run_id": "${C1_RUN_ID}_FAILURE",
  "reason": "Limit > \$10k require manager approval",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}]
EOF

# Build Packs
bash "$ROOT/scripts/audit/build_evidence_pack_v1.sh" --run-dir "$SUCCESS_DIR" --out-dir "$C1_DIR/pack_success" >/dev/null 2>&1
bash "$ROOT/scripts/audit/build_evidence_pack_v1.sh" --run-dir "$FAILURE_DIR" --out-dir "$C1_DIR/pack_failure" >/dev/null 2>&1

echo "   Status: Done -> $C1_DIR"

# -----------------------------------------------------------------------------
# Client-2: Moderation (Platform)
# -----------------------------------------------------------------------------
echo ">> Client-2: Moderation..."
C2_RUN_ID="RUN_CLIENT2_MODERATION_${TS}"
C2_DIR="$ROOT/out/p_runs/$C2_RUN_ID"
mkdir -p "$C2_DIR"

# 1. Failure Run (Perma-ban w/o Appeal)
echo "   - Simulating Failure (Perma-ban w/o Appeal Path)"
MOD_FAIL_DIR="$C2_DIR/failure"
mkdir -p "$MOD_FAIL_DIR"
cat > "$MOD_FAIL_DIR/run_manifest.json" <<EOF
{
  "run_id": "${C2_RUN_ID}_FAILURE",
  "client": "client-2-moderation",
  "scenario": "perma_ban",
  "result": "denied",
  "evidence": null,
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
# Dummy CE
cat > "$MOD_FAIL_DIR/Counterexamples_v1.json" <<EOF
[{
  "counterexample_id": "CE-PERMA-BAN-DENIED-${TS}",
  "kind": "CE_PERMA_BAN_DENIED_NO_APPEAL_PATH",
  "run_id": "${C2_RUN_ID}_FAILURE",
  "reason": "Permanent ban requires appeal URL in metadata",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}]
EOF

# Build Pack
bash "$ROOT/scripts/audit/build_evidence_pack_v1.sh" --run-dir "$MOD_FAIL_DIR" --out-dir "$C2_DIR/pack_failure" >/dev/null 2>&1

echo "   Status: Done -> $C2_DIR"
echo "=============================================="
