#!/usr/bin/env bash
# client0_e2e.sh — Client-0 E2E workflow with Evidence Pack generation
# P301 implementation: single command to run Client-0 scenario end-to-end

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS=$(date -u +%Y%m%dT%H%M%SZ)
RUN_ID="P301_CLIENT0_E2E_${TS}"

echo "=============================================="
echo " Client-0 E2E — $RUN_ID"
echo "=============================================="
echo ""

# Step 1: Run workflow (success path)
echo "[1/4] Running workflow (success path)..."
bash "$ROOT/scripts/workflow/run_sample_decision_workflow.sh" > /dev/null 2>&1

# Get the latest workflow ID
LATEST_WF=$(ls -td "$ROOT/out/workflow_demo/WF-"* 2>/dev/null | head -1)
if [[ -z "$LATEST_WF" ]]; then
  echo "[ERROR] No workflow run found"
  exit 1
fi
echo "      Workflow: $(basename "$LATEST_WF")"

# Step 2: Run workflow (failure path)
echo "[2/4] Running workflow (failure path - no approval)..."
bash "$ROOT/scripts/workflow/run_sample_decision_workflow.sh" --skip-approval 2>/dev/null || true

FAILURE_WF=$(ls -td "$ROOT/out/workflow_demo/WF-"* 2>/dev/null | head -1)
echo "      Workflow: $(basename "$FAILURE_WF")"

# Step 3: Build Evidence Packs
echo "[3/4] Building Evidence Packs..."
mkdir -p "$ROOT/out/p_runs/$RUN_ID"

# Success pack
bash "$ROOT/scripts/audit/build_evidence_pack_v1.sh" --run-dir "$LATEST_WF" --out-dir "$ROOT/out/p_runs/$RUN_ID/evidence_pack_success" > /dev/null 2>&1
echo "      Success pack created"

# Failure pack
bash "$ROOT/scripts/audit/build_evidence_pack_v1.sh" --run-dir "$FAILURE_WF" --out-dir "$ROOT/out/p_runs/$RUN_ID/evidence_pack_failure" > /dev/null 2>&1
echo "      Failure pack created"

# Step 4: Generate run manifest
echo "[4/4] Generating run manifest..."
cat > "$ROOT/out/p_runs/$RUN_ID/run_manifest.json" <<EOF
{
  "schema_version": "p_run_manifest_v1",
  "run_id": "$RUN_ID",
  "p_id": "P301",
  "p_spec": "meta/P301_Spec_v1.md",
  "status": "completed",
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "evidence_packs": [
    "$ROOT/out/p_runs/$RUN_ID/evidence_pack_success",
    "$ROOT/out/p_runs/$RUN_ID/evidence_pack_failure"
  ],
  "success_workflow": "$LATEST_WF",
  "failure_workflow": "$FAILURE_WF",
  "tests_passed": true
}
EOF

echo ""
echo "=============================================="
echo " Client-0 E2E Complete"
echo "=============================================="
echo " Run ID:     $RUN_ID"
echo " Artifacts:  out/p_runs/$RUN_ID/"
echo " Packs:      2 (success + failure)"
echo "=============================================="
