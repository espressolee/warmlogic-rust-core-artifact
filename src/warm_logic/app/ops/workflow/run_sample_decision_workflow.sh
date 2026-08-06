#!/usr/bin/env bash
# run_sample_decision_workflow.sh — Sample 3-phase workflow with veto gate
# Demonstrates: draft_generation → human_review (phase_witness) → apply_external (veto gate)
#
# Usage:
#   bash scripts/workflow/run_sample_decision_workflow.sh          # Run with approval
#   bash scripts/workflow/run_sample_decision_workflow.sh --skip-approval  # Simulate no approval (fails at phase 2)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS=$(date -u +%Y%m%dT%H%M%SZ)
WORKFLOW_ID="WF-LLM-LIMIT-CHANGE-${TS}"
OUT_DIR="${ROOT}/out/workflow_demo/${WORKFLOW_ID}"

mkdir -p "$OUT_DIR"

SKIP_APPROVAL="${1:-}"

echo "=============================================="
echo " Sample Decision Workflow: ${WORKFLOW_ID}"
echo "=============================================="

# -----------------------------------------------------------------------------
# Phase 1: draft_generation (sandbox, no veto)
# -----------------------------------------------------------------------------
echo ""
echo "[Phase 1] draft_generation (sandbox)..."

PHASE1_OUT="${OUT_DIR}/phase1_draft"
mkdir -p "$PHASE1_OUT"

cat > "$PHASE1_OUT/draft_output.json" <<EOF
{
  "workflow_id": "${WORKFLOW_ID}",
  "phase_id": "draft_generation",
  "phase_sequence": 0,
  "generated_by": "llm_model_v1",
  "proposal": {
    "action": "increase_customer_limit",
    "customer_id": "CUST-12345",
    "current_limit": 10000,
    "proposed_limit": 15000,
    "justification": "Customer has good payment history"
  },
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# Compute output hash
DRAFT_HASH=$(shasum -a 256 "$PHASE1_OUT/draft_output.json" | cut -d' ' -f1)
echo "$DRAFT_HASH  draft_output.json" > "$PHASE1_OUT/output.sha256"
echo "[Phase 1] ✓ Draft generated (hash: ${DRAFT_HASH:0:16}...)"

# -----------------------------------------------------------------------------
# Phase 2: human_review (requires phase_witness)
# -----------------------------------------------------------------------------
echo ""
echo "[Phase 2] human_review (requires attestation)..."

PHASE2_OUT="${OUT_DIR}/phase2_review"
mkdir -p "$PHASE2_OUT"

if [[ "$SKIP_APPROVAL" == "--skip-approval" ]]; then
  echo "[Phase 2] ✗ SKIPPED - No human approval (simulating missing witness)"

  # Generate CE for missing witness
  cat > "$PHASE2_OUT/Counterexamples_v1.json" <<EOF
[{
  "counterexample_id": "CE-WORKFLOW-PHASE-WITNESS-MISSING-${WORKFLOW_ID}-P2",
  "kind": "CE_WORKFLOW_PHASE_WITNESS_MISSING",
  "workflow_id": "${WORKFLOW_ID}",
  "phase_id": "human_review",
  "reason": "Phase advanced without required attestation",
  "detected_by": "workflow_runner_v1",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}]
EOF

  echo "[Phase 2] CE generated: CE_WORKFLOW_PHASE_WITNESS_MISSING"
  echo "[Workflow] FAILED at Phase 2 - Missing witness"
  echo "1" > "$OUT_DIR/exitcode.txt"
  exit 1
else
  # Generate phase_witness for human_review
  cat > "$PHASE2_OUT/phase_witness.json" <<EOF
{
  "schema_version": "phase_witness_v1",
  "workflow_id": "${WORKFLOW_ID}",
  "phase_id": "human_review",
  "phase_sequence": 1,
  "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "attestation": {
    "attester_id": "reviewer-001",
    "attester_type": "human",
    "signature": null
  },
  "input_hash": "${DRAFT_HASH}",
  "output_hash": null,
  "evidence_bundle_path": null,
  "next_phase_id": "apply_to_api",
  "veto_gate_required": true
}
EOF
  echo "[Phase 2] ✓ Human review completed (attester: reviewer-001)"
fi

# -----------------------------------------------------------------------------
# Phase 3: apply_to_api (requires veto gate)
# -----------------------------------------------------------------------------
echo ""
echo "[Phase 3] apply_to_api (veto gate)..."

PHASE3_OUT="${OUT_DIR}/phase3_apply"
mkdir -p "$PHASE3_OUT"

# Create veto request with witness_path
cat > "$PHASE3_OUT/veto_request.json" <<EOF
{
  "schema_version": "veto_request_v1",
  "org_id": "demo-org",
  "tenant_id": "demo-tenant",
  "run_id": "${WORKFLOW_ID}",
  "intent": "apply_limit_change",
  "action": "update_customer_limit",
  "witness_path": "${PHASE2_OUT}/phase_witness.json",
  "evidence_bundle_sha256": "${DRAFT_HASH}",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# Call veto gateway
echo "[Phase 3] Evaluating veto request..."
python3 "${ROOT}/runtime/veto_gateway/evaluate_veto_request_v1.py" \
  --request "$PHASE3_OUT/veto_request.json" \
  --out-dir "$PHASE3_OUT"

VETO_EXIT=$?
ALLOW=$(python3 -c "import json; print(json.load(open('$PHASE3_OUT/veto_decision.json'))['allow'])")

if [[ "$ALLOW" == "True" ]]; then
  echo "[Phase 3] ✓ Veto gate PASSED - External API call allowed"

  # Simulate external API call (mock)
  cat > "$PHASE3_OUT/api_response.json" <<EOF
{
  "status": "success",
  "action": "customer_limit_updated",
  "customer_id": "CUST-12345",
  "new_limit": 15000,
  "applied_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

  echo "[Phase 3] ✓ External API call completed (mock)"
  FINAL_STATUS="DONE"
else
  echo "[Phase 3] ✗ Veto gate DENIED"
  FINAL_STATUS="FAIL_VETO"
fi

# -----------------------------------------------------------------------------
# Workflow Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo " Workflow Summary"
echo "=============================================="
echo " Workflow ID: ${WORKFLOW_ID}"
echo " Status: ${FINAL_STATUS}"
echo " Artifacts: ${OUT_DIR}"
echo ""
echo " Phases:"
echo "   [1] draft_generation: ✓"
echo "   [2] human_review: ✓ (witness: ${PHASE2_OUT}/phase_witness.json)"
echo "   [3] apply_to_api: $([ "$FINAL_STATUS" == "DONE" ] && echo "✓" || echo "✗")"
echo "=============================================="

# Write final manifest
cat > "$OUT_DIR/workflow_manifest.json" <<EOF
{
  "workflow_id": "${WORKFLOW_ID}",
  "status": "${FINAL_STATUS}",
  "phases_completed": 3,
  "veto_gate_passed": $([ "$FINAL_STATUS" == "DONE" ] && echo "true" || echo "false"),
  "artifacts": {
    "phase1": "${PHASE1_OUT}",
    "phase2": "${PHASE2_OUT}",
    "phase3": "${PHASE3_OUT}"
  },
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "0" > "$OUT_DIR/exitcode.txt"
echo "[OK] Workflow demo completed -> ${OUT_DIR}"
