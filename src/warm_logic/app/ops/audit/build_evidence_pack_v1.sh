#!/usr/bin/env bash
# build_evidence_pack_v1.sh — Build Evidence Pack v1 for external delivery
#
# Evidence Pack v1 Structure:
#   /run/       - run_manifest, config, env
#   /ce/        - CE ledger, fail-open, appeals
#   /metrics/   - SLI, legitimacy
#   /reports/   - verify_report, eval_report
#   /repro/     - reproduction scripts (run.sh, verify.sh)
#   README.md   - Pack documentation
#   MANIFEST.sha256 - Hash manifest
#
# Usage:
#   bash scripts/audit/build_evidence_pack_v1.sh --run-id RUN_123
#   bash scripts/audit/build_evidence_pack_v1.sh --run-dir out/workflow_demo/WF-xxx

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS=$(date -u +%Y%m%dT%H%M%SZ)

# Parse arguments
RUN_ID=""
RUN_DIR=""
OUT_DIR=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --run-id)
      RUN_ID="$2"
      shift 2
      ;;
    --run-dir)
      RUN_DIR="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Determine run info
if [[ -n "$RUN_DIR" ]]; then
  RUN_ID=$(basename "$RUN_DIR")
elif [[ -n "$RUN_ID" ]]; then
  RUN_DIR="${ROOT}/out/run_results/${RUN_ID}"
else
  echo "Error: --run-id or --run-dir required"
  exit 1
fi

if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="${ROOT}/out/evidence_packs/${RUN_ID}_${TS}"
fi

echo "=============================================="
echo " Building Evidence Pack v1"
echo "=============================================="
echo " Run ID:  ${RUN_ID}"
echo " Run Dir: ${RUN_DIR}"
echo " Out Dir: ${OUT_DIR}"
echo "=============================================="

# Create pack structure
mkdir -p "$OUT_DIR"/{run,ce,metrics,reports,repro}

# Copy artifacts (if exist)
copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    cp -r "$src" "$dst"
    echo "[pack] Copied: $(basename "$src")"
  fi
}

# Run artifacts
copy_if_exists "$RUN_DIR/run_manifest.json" "$OUT_DIR/run/"
copy_if_exists "$RUN_DIR/workflow_manifest.json" "$OUT_DIR/run/"
copy_if_exists "$RUN_DIR/config.json" "$OUT_DIR/run/"
copy_if_exists "$RUN_DIR/env.json" "$OUT_DIR/run/"

# CE artifacts
copy_if_exists "$RUN_DIR/ce_ledger.jsonl" "$OUT_DIR/ce/"
copy_if_exists "$RUN_DIR/Counterexamples_v1.json" "$OUT_DIR/ce/"

# Look for phase-level CE
for phase_dir in "$RUN_DIR"/phase*; do
  if [[ -d "$phase_dir" ]]; then
    copy_if_exists "$phase_dir/Counterexamples_v1.json" "$OUT_DIR/ce/$(basename "$phase_dir")_Counterexamples_v1.json"
    copy_if_exists "$phase_dir/veto_decision.json" "$OUT_DIR/ce/$(basename "$phase_dir")_veto_decision.json"
  fi
done

# Metrics
copy_if_exists "$RUN_DIR/legitimacy_metrics.json" "$OUT_DIR/metrics/"
copy_if_exists "$RUN_DIR/sli_metrics.json" "$OUT_DIR/metrics/"

# Collect legitimacy metrics if not present
if [[ ! -f "$OUT_DIR/metrics/legitimacy_metrics.json" ]]; then
  echo "[pack] Collecting legitimacy metrics..."
  python3 "${ROOT}/scripts/audit/collect_legitimacy_metrics.py" \
    --run-id "$RUN_ID" \
    --run-dir "$RUN_DIR" \
    --out-dir "$OUT_DIR/metrics" 2>/dev/null || true
fi

# Reports
copy_if_exists "$RUN_DIR/verify_report.json" "$OUT_DIR/reports/"
copy_if_exists "$RUN_DIR/eval_report.json" "$OUT_DIR/reports/"

# Create repro scripts
cat > "$OUT_DIR/repro/run.sh" <<EOF
#!/usr/bin/env bash
# Reproduction script for ${RUN_ID}
# Generated: ${TS}
set -euo pipefail

echo "Reproduction not yet implemented for this run type"
echo "Original run directory: ${RUN_DIR}"
EOF
chmod +x "$OUT_DIR/repro/run.sh"

cat > "$OUT_DIR/repro/verify.sh" <<EOF
#!/usr/bin/env bash
# Verification script for ${RUN_ID}
# Generated: ${TS}
set -euo pipefail

cd "\$(dirname "\$0")/.."
echo "Verifying Evidence Pack: ${RUN_ID}"
sha256sum -c MANIFEST.sha256 && echo "OK: All hashes match" || echo "FAIL: Hash mismatch"
EOF
chmod +x "$OUT_DIR/repro/verify.sh"

# Create README
cat > "$OUT_DIR/README.md" <<EOF
# Evidence Pack v1: ${RUN_ID}

Generated: ${TS}

## Structure

\`\`\`
/run/       - Run configuration and manifests
/ce/        - Counterexample ledger and veto decisions
/metrics/   - Legitimacy and SLI metrics
/reports/   - Verification and evaluation reports
/repro/     - Reproduction scripts
\`\`\`

## Verification

\`\`\`bash
cd ${RUN_ID}
bash repro/verify.sh
\`\`\`

## References

- WHO_PAYS_THE_COST: docs/legitimacy/WHO_PAYS_THE_COST_v1.md
- LEGITIMACY_METRICS_MAPPING: docs/legitimacy/LEGITIMACY_METRICS_MAPPING_v1.md
- Evidence Pack Spec: docs/product/Evidence_Pack_v1_Spec.md

## Non-goals

- This pack does NOT claim regulatory compliance
- This pack does NOT guarantee safety
- This pack is for audit/evidence purposes only
EOF

# Generate hash manifest
echo "[pack] Generating hash manifest..."
cd "$OUT_DIR"
find . -type f ! -name "MANIFEST.sha256" -exec sha256sum {} \; | sort > MANIFEST.sha256
cd - > /dev/null

# Create tar archive
ARCHIVE="${OUT_DIR}.tar.gz"
tar -czf "$ARCHIVE" -C "$(dirname "$OUT_DIR")" "$(basename "$OUT_DIR")"

echo ""
echo "=============================================="
echo " Evidence Pack v1 Complete"
echo "=============================================="
echo " Pack Dir:  ${OUT_DIR}"
echo " Archive:   ${ARCHIVE}"
echo " Manifest:  ${OUT_DIR}/MANIFEST.sha256"
echo "=============================================="
