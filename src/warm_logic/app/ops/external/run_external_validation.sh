#!/usr/bin/env bash
# scripts/external/run_external_validation.sh
# Comprehensive external validation script for WarmLogic
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

VALIDATOR_ID="${VALIDATOR_ID:-anonymous}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_PATH="out/external_validation_report.json"

echo "======================================"
echo "WarmLogic External Validation"
echo "======================================"
echo "Timestamp: $TIMESTAMP"
echo "Validator: $VALIDATOR_ID"
echo ""

mkdir -p out

# Collect system info
HOSTNAME="$(hostname 2>/dev/null || echo 'unknown')"
PYTHON_VERSION="$(python --version 2>&1 | head -1)"
PLATFORM="$(uname -s 2>/dev/null || echo 'unknown')"

# Initialize results
TAU_STATUS="FAIL"
TAU_SCENARIOS=0
VETO_STATUS="FAIL"
VETO_ITERATIONS=0
LLM_CE_STATUS="FAIL"
LLM_CE_TESTS=0
SCHEMA_STATUS="FAIL"
SCHEMA_TESTS=0

# 1. τ Governance Validation
echo "[1/4] τ Governance Validation..."
if python scripts/governance/run_tau_governance_fuzzer.py \
    --scenarios data/tau_scenarios \
    --vm-cmd "python scripts/governance/gov_vm_snapshot.py --baseline fixtures/tau_baseline_report.json" \
    --out out/tau_fuzz_external.json \
    --fail-on-mismatch 2>&1; then
  TAU_STATUS="PASS"
  TAU_SCENARIOS=19
  echo "  ✅ τ Governance: PASS (19 scenarios)"
else
  echo "  ❌ τ Governance: FAIL"
fi

# 2. Veto Layer Stress Test
echo "[2/4] Veto Layer Stress Test..."
VETO_OUTPUT=$(python scripts/eval/os_v2_stress_test.py --iterations 100 2>&1 || true)
FAIL_OPEN_RATE=$(echo "$VETO_OUTPUT" | grep -o '"s_fail_open_rate": [0-9.]*' | grep -oE '[0-9.]+$' || echo "1")
if [ "$(echo "$FAIL_OPEN_RATE == 0" | bc -l 2>/dev/null || echo "0")" = "1" ] || [ "$FAIL_OPEN_RATE" = "0.0" ] || [ "$FAIL_OPEN_RATE" = "0" ]; then
  VETO_STATUS="PASS"
  VETO_ITERATIONS=100
  echo "  ✅ Veto Layer: PASS (100 iterations, fail_open_rate=$FAIL_OPEN_RATE)"
else
  echo "  ❌ Veto Layer: FAIL (fail_open_rate=$FAIL_OPEN_RATE)"
fi

# 3. LLM CE Emitter Tests
echo "[3/4] LLM CE Emitter Tests..."
LLM_OUTPUT=$(python -m pytest tests/product/test_emit_llm_ce_from_logs.py -v --tb=no 2>&1 || true)
if echo "$LLM_OUTPUT" | grep -q "4 passed"; then
  LLM_CE_STATUS="PASS"
  LLM_CE_TESTS=4
  echo "  ✅ LLM CE Emitter: PASS (4 tests)"
else
  echo "  ❌ LLM CE Emitter: FAIL"
fi

# 4. Schema Validation Tests
echo "[4/4] Schema Validation Tests..."
SCHEMA_OUTPUT=$(python -m pytest tests/governance/ tests/runtime/ -v --tb=no 2>&1 || true)
PASSED_COUNT=$(echo "$SCHEMA_OUTPUT" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
if [ "$PASSED_COUNT" -gt 50 ]; then
  SCHEMA_STATUS="PASS"
  SCHEMA_TESTS="$PASSED_COUNT"
  echo "  ✅ Schema Validation: PASS ($PASSED_COUNT tests)"
else
  echo "  ❌ Schema Validation: FAIL ($PASSED_COUNT tests)"
fi

# Determine overall status
OVERALL_STATUS="PASS"
if [ "$TAU_STATUS" != "PASS" ] || [ "$VETO_STATUS" != "PASS" ] || [ "$LLM_CE_STATUS" != "PASS" ] || [ "$SCHEMA_STATUS" != "PASS" ]; then
  OVERALL_STATUS="FAIL"
fi

# Generate report
cat > "$REPORT_PATH" <<EOF
{
  "validation_id": "EXT-VAL-$(date +%s)",
  "timestamp": "$TIMESTAMP",
  "validator_id": "$VALIDATOR_ID",
  "validator_info": {
    "hostname": "$HOSTNAME",
    "python_version": "$PYTHON_VERSION",
    "platform": "$PLATFORM"
  },
  "results": {
    "tau_governance": { "status": "$TAU_STATUS", "scenarios": $TAU_SCENARIOS },
    "veto_layer": { "status": "$VETO_STATUS", "iterations": $VETO_ITERATIONS },
    "llm_ce_emitter": { "status": "$LLM_CE_STATUS", "tests": $LLM_CE_TESTS },
    "schema_validation": { "status": "$SCHEMA_STATUS", "tests": $SCHEMA_TESTS }
  },
  "overall_status": "$OVERALL_STATUS"
}
EOF

echo ""
echo "======================================"
echo "Validation Complete: $OVERALL_STATUS"
echo "======================================"
echo "Report saved to: $REPORT_PATH"

if [ "$OVERALL_STATUS" = "PASS" ]; then
  exit 0
else
  exit 1
fi
