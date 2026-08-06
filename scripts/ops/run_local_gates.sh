#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"   # all / log / pieces / quick

run_all() {
  rm -rf \
    out/audit_spine_demo \
    out/audit_spine_v1 \
    out/cases/mcp_metaobs/W4_CT_SCENARIO_SWEEP_LOAD || true

  make -s audit-spine-demo || echo "[WARN] audit-spine-demo FAILED ($?)"
  make -s audit-spine-v1   || echo "[WARN] audit-spine-v1 FAILED ($?)"

  WL_CASE_REQUIRE_REAL=1 \
    bash cases/mcp_metaobs/W4_CT_SCENARIO_SWEEP_LOAD/run_script.sh \
    || echo "[WARN] W4 CT SCENARIO SWEEP LOAD FAILED ($?)"

  python scripts/ci/check_mcp_decision_correlation.py \
    || echo "[WARN] check_mcp_decision_correlation FAILED ($?)"

  echo "[INFO] DONE (all)"
}

run_log() {
  mkdir -p out
  # On failure the script still exits 0; check the log for the outcome.
  bash -lc '
    set -euo pipefail
    rm -rf out/audit_spine_demo out/audit_spine_v1 out/cases/mcp_metaobs/W4_CT_SCENARIO_SWEEP_LOAD || true
    make -s audit-spine-demo
    make -s audit-spine-v1
    WL_CASE_REQUIRE_REAL=1 bash cases/mcp_metaobs/W4_CT_SCENARIO_SWEEP_LOAD/run_script.sh
    python scripts/ci/check_mcp_decision_correlation.py
  ' > out/run_all_gates.log 2>&1 || true

  echo "[INFO] tail of out/run_all_gates.log:"
  tail -n 200 out/run_all_gates.log || true
}

run_pieces() {
  rm -rf out/audit_spine_demo && make -s audit-spine-demo
  rm -rf out/audit_spine_v1   && make -s audit-spine-v1
  WL_CASE_REQUIRE_REAL=1 bash cases/mcp_metaobs/W4_CT_SCENARIO_SWEEP_LOAD/run_script.sh
  python scripts/ci/check_mcp_decision_correlation.py
}

run_quick() {
  python scripts/ci/check_schema_registry.py
  python scripts/ci/check_normative_contract_ir_instances_v1.py
  python scripts/ci/check_observability_policy_contract_v1.py
  python scripts/ci/check_otel_scope_contract_v1.py
  python scripts/ci/check_audit_pack_contract_v1.py
  python scripts/ci/check_archive_meta_boundary_v1.py
  python scripts/ci/check_archive_import_index_v1.py
  python scripts/ci/check_no_stray_govdec_memos_v1.py
  python scripts/ci/check_wlpv4_contract_gate.py --out out/wlpv4_contract_gate_report.json
  python scripts/ci/generate_program_progress_latest_v1.py --check
  python scripts/devloop/prove_p3xx_gate_closed_v1.py --out-dir out/p_status_gate/P3XX_GATE_CLOSED_RUN_v1 --p 301
  python scripts/ci/check_audit_pack_instances_v1.py --max 1
  python scripts/ci/check_mcp_surface_contract_v1.py
  python scripts/ci/check_mcp_event_schema.py
  python scripts/ci/check_meta_obs_schema.py
  python scripts/ci/check_mcp_decision_correlation.py
}

case "$MODE" in
  all)
    run_all
    ;;
  log)
    run_log
    ;;
  pieces)
    run_pieces
    ;;
  quick)
    run_quick
    ;;
  *)
    echo "Usage: $0 {all|log|pieces|quick}" >&2
    exit 1
    ;;
esac
