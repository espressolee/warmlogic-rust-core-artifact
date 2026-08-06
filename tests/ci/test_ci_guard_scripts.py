"""Regression tests for CI guard scripts in scripts/ci."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.ci import (
    check_rust_clippy_changed_files,
    check_parallel_git_ops,
    check_test_skip_policy,
    check_junit_summary,
    check_coverage_ratchet,
    check_readme_truth,
    check_soft_gate_budget,
    check_top_tier_policy,
    validate_ci_evidence,
    write_ci_evidence,
)


def _future_expiry() -> str:
    # Fixtures that model a *valid* allowlist entry must not age out.
    return (date.today() + timedelta(days=365)).isoformat()


def test_write_ci_evidence_parse_job_results_ok() -> None:
    out = write_ci_evidence.parse_job_results(["lint=success", "test=fail"])
    assert out == {"lint": "success", "test": "fail"}


def test_write_ci_evidence_parse_job_results_invalid() -> None:
    with pytest.raises(ValueError, match="invalid --job-result value"):
        write_ci_evidence.parse_job_results(["lint-success"])


def test_write_ci_evidence_main_writes_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "evidence.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "write_ci_evidence.py",
            "--out",
            str(out),
            "--gate",
            "ci-main",
            "--workflow",
            "CI Main",
            "--run-id",
            "123",
            "--run-attempt",
            "1",
            "--event-name",
            "workflow_dispatch",
            "--ref",
            "refs/heads/main",
            "--sha",
            "deadbeef",
            "--job-status",
            "pass",
            "--job-result",
            "lint=success",
            "--job-result",
            "test-python=success",
        ],
    )

    write_ci_evidence.main()
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema"] == "warmlogic.ci.evidence.v1"
    assert payload["gate"] == "ci-main"
    assert payload["job_status"] == "pass"
    assert payload["job_results"]["lint"] == "success"
    assert payload["job_results"]["test-python"] == "success"


def test_validate_ci_evidence_accepts_valid_payload() -> None:
    payload = {
        "schema": "warmlogic.ci.evidence.v1",
        "generated_at_utc": "2026-02-13T00:00:00+00:00",
        "gate": "ci-main",
        "workflow": "CI Main",
        "run_id": "123",
        "run_attempt": "1",
        "event_name": "workflow_dispatch",
        "ref": "refs/heads/main",
        "sha": "deadbeef",
        "job_status": "pass",
        "job_results": {"lint": "success"},
    }
    contract = {
        "expected_schema": "warmlogic.ci.evidence.v1",
        "required_top_level_fields": list(payload.keys()),
        "required_non_empty_string_fields": [
            "schema",
            "generated_at_utc",
            "gate",
            "workflow",
            "run_id",
            "run_attempt",
            "event_name",
            "ref",
            "sha",
            "job_status",
        ],
        "allowed_job_status": ["pass", "fail"],
        "min_job_results": 1,
    }
    validate_ci_evidence.validate(payload, contract)


def test_validate_ci_evidence_rejects_invalid_status() -> None:
    payload = {
        "schema": "warmlogic.ci.evidence.v1",
        "generated_at_utc": "2026-02-13T00:00:00+00:00",
        "gate": "ci-main",
        "workflow": "CI Main",
        "run_id": "123",
        "run_attempt": "1",
        "event_name": "workflow_dispatch",
        "ref": "refs/heads/main",
        "sha": "deadbeef",
        "job_status": "unknown",
        "job_results": {"lint": "success"},
    }
    contract = {
        "expected_schema": "warmlogic.ci.evidence.v1",
        "required_top_level_fields": list(payload.keys()),
        "required_non_empty_string_fields": [
            "schema",
            "generated_at_utc",
            "gate",
            "workflow",
            "run_id",
            "run_attempt",
            "event_name",
            "ref",
            "sha",
            "job_status",
        ],
        "allowed_job_status": ["pass", "fail"],
        "min_job_results": 1,
    }
    with pytest.raises(SystemExit):
        validate_ci_evidence.validate(payload, contract)


def test_check_junit_summary_enforce_ok() -> None:
    counts = {"tests": 10, "failures": 0, "errors": 0, "skipped": 0}
    check_junit_summary.enforce(
        counts,
        max_skipped=0,
        max_failures=0,
        max_errors=0,
        min_tests=1,
    )


def test_check_junit_summary_enforce_skipped_fails() -> None:
    counts = {"tests": 10, "failures": 0, "errors": 0, "skipped": 1}
    with pytest.raises(SystemExit):
        check_junit_summary.enforce(
            counts,
            max_skipped=0,
            max_failures=0,
            max_errors=0,
            min_tests=1,
        )


def test_coverage_ratchet_percent_parsing_ok() -> None:
    observed = check_coverage_ratchet.get_percent_covered(
        {"totals": {"percent_covered": "42.5"}}
    )
    assert observed == pytest.approx(42.5)


def test_coverage_ratchet_percent_parsing_missing_totals() -> None:
    with pytest.raises(SystemExit):
        check_coverage_ratchet.get_percent_covered({})


def test_soft_gate_classify_counts() -> None:
    lines = [
        ".github/workflows/a.yml:1: foo || true",
        ".github/workflows/b.yml:2: continue-on-error: true",
        ".github/workflows/c.yml:3: bandit --exit-zero",
    ]
    counts = check_soft_gate_budget.classify(lines)
    assert counts["|| true"] == 1
    assert counts["continue-on-error: true"] == 1
    assert counts["--exit-zero"] == 1


def test_soft_gate_allowlist_violation_fails() -> None:
    budget = {"allowlist": {"continue-on-error: true": [".github/workflows/a.yml"]}}
    lines = [".github/workflows/b.yml:2: continue-on-error: true"]
    with pytest.raises(SystemExit):
        check_soft_gate_budget.enforce_allowlist(lines, budget)


def test_soft_gate_allowlist_permits() -> None:
    budget = {"allowlist": {"continue-on-error: true": [".github/workflows/a.yml"]}}
    lines = [".github/workflows/a.yml:2: continue-on-error: true"]
    check_soft_gate_budget.enforce_allowlist(lines, budget)


def test_rust_clippy_changed_normalize_path() -> None:
    normalized = check_rust_clippy_changed_files.normalize_file_path(
        "/home/runner/work/WarmLogic/WarmLogic/rust_core/src/consensus/bft.rs"
    )
    assert normalized == "src/consensus/bft.rs"


def test_rust_clippy_changed_filter_only_changed_files() -> None:
    changed = {"src/consensus/bft.rs"}
    diagnostics = [
        {"file": "src/consensus/bft.rs", "line": 75, "message": "this impl can be derived"},
        {"file": "src/net/nat.rs", "line": 1, "message": "unused field"},
    ]
    offenders = check_rust_clippy_changed_files.filter_changed_file_diagnostics(
        changed, diagnostics
    )
    assert len(offenders) == 1
    assert offenders[0]["file"] == "src/consensus/bft.rs"


def test_rust_clippy_changed_extract_diagnostics(tmp_path: Path) -> None:
    jsonl = tmp_path / "clippy.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "reason": "compiler-message",
                        "message": {
                            "level": "error",
                            "message": "this `impl` can be derived",
                            "spans": [
                                {
                                    "file_name": "rust_core/src/consensus/bft.rs",
                                    "line_start": 75,
                                    "is_primary": True,
                                }
                            ],
                        },
                    }
                ),
                json.dumps({"reason": "build-finished", "success": False}),
                "",
            ]
        ),
        encoding="utf-8",
    )

    diagnostics, build_success = check_rust_clippy_changed_files.extract_diagnostics(jsonl)
    assert build_success is False
    assert len(diagnostics) == 1
    assert diagnostics[0]["file"] == "src/consensus/bft.rs"
    assert diagnostics[0]["line"] == 75


def test_readme_truth_badge_parser() -> None:
    content = "![version](https://img.shields.io/badge/version-1.2.3-blue)"
    assert check_readme_truth.parse_readme_badge_version(content) == "1.2.3"


def test_top_tier_policy_soft_gate_detection() -> None:
    with pytest.raises(SystemExit):
        check_top_tier_policy.check_no_soft_gates(
            Path("dummy.yml"), "steps:\n  - run: pytest || true\n"
        )


def test_top_tier_policy_security_workflow_requires_policy_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wf = tmp_path / ".github" / "workflows" / "ci-security.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text(
        "pip-audit\n"
        "cargo deny check\n"
        "python scripts/ci/check_parallel_git_ops.py\n"
        "python scripts/ci/check_test_skip_policy.py\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_top_tier_policy, "ROOT", tmp_path)
    check_top_tier_policy.check_security_workflow()


def test_top_tier_policy_security_workflow_missing_policy_step_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wf = tmp_path / ".github" / "workflows" / "ci-security.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text(
        "pip-audit\n"
        "cargo deny check\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_top_tier_policy, "ROOT", tmp_path)
    with pytest.raises(SystemExit):
        check_top_tier_policy.check_security_workflow()


def test_top_tier_policy_production_workflow_requires_policy_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wf = tmp_path / ".github" / "workflows" / "ci-production-gate.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text(
        "python scripts/ci/check_parallel_git_ops.py\n"
        "python scripts/ci/check_test_skip_policy.py\n"
        "WARM_RUN_MESH_E2E=1 pytest -q -W error -ra tests/e2e/test_mesh_sync.py::test_gossip_propagation\n"
        "WARM_UI_BASE_URL=http://127.0.0.1:8011 pytest -q -W error -ra tests/security/test_constitutional_e2e.py::TestConstitutionalE2E::test_e2e_api_guard\n"
        "WARM_RUN_MESH_E2E=1 WARM_UI_BASE_URL=http://127.0.0.1:8011 pytest -n auto -q -W error -ra\n"
        "--junitxml /tmp/warmlogic_strict_full.junit.xml\n"
        "python scripts/ci/check_junit_summary.py\n"
        "--max-skipped 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_top_tier_policy, "ROOT", tmp_path)
    check_top_tier_policy.check_production_gate_workflow()


def test_top_tier_policy_production_workflow_missing_policy_step_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wf = tmp_path / ".github" / "workflows" / "ci-production-gate.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text(
        "WARM_RUN_MESH_E2E=1 pytest -q -W error -ra tests/e2e/test_mesh_sync.py::test_gossip_propagation\n"
        "WARM_UI_BASE_URL=http://127.0.0.1:8011 pytest -q -W error -ra tests/security/test_constitutional_e2e.py::TestConstitutionalE2E::test_e2e_api_guard\n"
        "WARM_RUN_MESH_E2E=1 WARM_UI_BASE_URL=http://127.0.0.1:8011 pytest -n auto -q -W error -ra\n"
        "--junitxml /tmp/warmlogic_strict_full.junit.xml\n"
        "python scripts/ci/check_junit_summary.py\n"
        "--max-skipped 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_top_tier_policy, "ROOT", tmp_path)
    with pytest.raises(SystemExit):
        check_top_tier_policy.check_production_gate_workflow()


def test_top_tier_policy_main_workflow_requires_policy_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ci_main = tmp_path / "ci-main.yml"
    ci_main.write_text(
        "python scripts/ci/check_parallel_git_ops.py\n"
        "python scripts/ci/check_test_skip_policy.py\n"
        "--cov-report=json\n"
        "python scripts/ci/check_coverage_ratchet.py\n",
        encoding="utf-8",
    )
    cfg = tmp_path / "coverage_ratchet.json"
    cfg.write_text('{"minimum_total_percent": 0}\n', encoding="utf-8")
    monkeypatch.setattr(check_top_tier_policy, "CI_MAIN", ci_main)
    monkeypatch.setattr(check_top_tier_policy, "COVERAGE_RATCHET_CONFIG", cfg)
    check_top_tier_policy.check_coverage_ratchet_policy()


def test_top_tier_policy_main_workflow_missing_policy_step_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ci_main = tmp_path / "ci-main.yml"
    ci_main.write_text(
        "--cov-report=json\n"
        "python scripts/ci/check_coverage_ratchet.py\n",
        encoding="utf-8",
    )
    cfg = tmp_path / "coverage_ratchet.json"
    cfg.write_text('{"minimum_total_percent": 0}\n', encoding="utf-8")
    monkeypatch.setattr(check_top_tier_policy, "CI_MAIN", ci_main)
    monkeypatch.setattr(check_top_tier_policy, "COVERAGE_RATCHET_CONFIG", cfg)
    with pytest.raises(SystemExit):
        check_top_tier_policy.check_coverage_ratchet_policy()


def test_top_tier_policy_ci_evidence_policy_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ci_main = tmp_path / "ci-main.yml"
    ci_security = tmp_path / "ci-security.yml"
    ci_prod = tmp_path / "ci-production-gate.yml"
    ci_evidence = tmp_path / "write_ci_evidence.py"
    ci_validator = tmp_path / "validate_ci_evidence.py"
    ci_contract = tmp_path / "ci_evidence_contract.json"

    ci_main.write_text(
        "scripts/ci/write_ci_evidence.py\n"
        "scripts/ci/validate_ci_evidence.py\n"
        "--gate ci-main\n"
        "--input artifacts/ci-evidence/ci-main.json\n"
        "name: ci-main-evidence\n",
        encoding="utf-8",
    )
    ci_security.write_text(
        "scripts/ci/write_ci_evidence.py\n"
        "scripts/ci/validate_ci_evidence.py\n"
        "--gate ci-security\n"
        "--input artifacts/ci-evidence/ci-security.json\n"
        "name: ci-security-evidence\n",
        encoding="utf-8",
    )
    ci_prod.write_text(
        "name: Write CI evidence (production gate)\nif: always()\n"
        "scripts/ci/write_ci_evidence.py\n"
        "scripts/ci/validate_ci_evidence.py\n"
        "--gate ci-production-gate\n"
        "--input artifacts/ci-evidence/ci-production-gate.json\n"
        "name: ci-production-gate-evidence\n",
        encoding="utf-8",
    )
    ci_evidence.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    ci_validator.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    ci_contract.write_text('{"expected_schema":"warmlogic.ci.evidence.v1"}\n', encoding="utf-8")

    monkeypatch.setattr(check_top_tier_policy, "CI_MAIN", ci_main)
    monkeypatch.setattr(check_top_tier_policy, "CI_SECURITY", ci_security)
    monkeypatch.setattr(check_top_tier_policy, "CI_PRODUCTION_GATE", ci_prod)
    monkeypatch.setattr(check_top_tier_policy, "CI_EVIDENCE_SCRIPT", ci_evidence)
    monkeypatch.setattr(
        check_top_tier_policy, "CI_EVIDENCE_VALIDATOR_SCRIPT", ci_validator
    )
    monkeypatch.setattr(check_top_tier_policy, "CI_EVIDENCE_CONTRACT", ci_contract)

    check_top_tier_policy.check_ci_evidence_policy()


def test_top_tier_policy_local_gate_repro_policy_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate_script = tmp_path / "run_local_top_tier_gate.sh"
    gate_script.write_text(
        "#!/usr/bin/env bash\n"
        "scripts/ci/check_junit_summary.py --max-skipped 0\n"
        "python scripts/ci/check_parallel_git_ops.py\n",
        encoding="utf-8",
    )
    junit_script = tmp_path / "check_junit_summary.py"
    junit_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    makefile = tmp_path / "Makefile"
    makefile.write_text(
        "ci-top-tier-policy:\n\t@echo ok\n"
        "ci-top-tier-local-fast:\n\t@echo ok\n"
        "ci-top-tier-local:\n\t@echo ok\n",
        encoding="utf-8",
    )

    runbook = tmp_path / "ci-evidence-gates.md"
    runbook.write_text(
        "make ci-top-tier-local-fast\nmake ci-top-tier-local\n", encoding="utf-8"
    )
    parallel_git_runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    parallel_git_runbook.write_text(
        "scripts/ops/git_mutex.sh\nscripts/ops/git_safe_commit.sh\n.git/index.lock\n",
        encoding="utf-8",
    )
    parallel_git_policy = tmp_path / "check_parallel_git_ops.py"
    parallel_git_policy.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    monkeypatch.setattr(check_top_tier_policy, "LOCAL_TOP_TIER_GATE_SCRIPT", gate_script)
    monkeypatch.setattr(check_top_tier_policy, "MAKEFILE", makefile)
    monkeypatch.setattr(check_top_tier_policy, "CI_EVIDENCE_RUNBOOK", runbook)
    monkeypatch.setattr(check_top_tier_policy, "JUNIT_SUMMARY_SCRIPT", junit_script)
    monkeypatch.setattr(
        check_top_tier_policy, "PARALLEL_GIT_RUNBOOK", parallel_git_runbook
    )
    monkeypatch.setattr(
        check_top_tier_policy, "PARALLEL_GIT_POLICY_SCRIPT", parallel_git_policy
    )

    check_top_tier_policy.check_local_gate_repro_policy()


def test_top_tier_policy_parallel_git_execution_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "check_parallel_git_ops.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "print('[PARALLEL-GIT-POLICY] OK')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_top_tier_policy, "PARALLEL_GIT_POLICY_SCRIPT", script)
    check_top_tier_policy.check_parallel_git_policy_execution()


def test_top_tier_policy_parallel_git_execution_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "check_parallel_git_ops.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "raise SystemExit(2)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_top_tier_policy, "PARALLEL_GIT_POLICY_SCRIPT", script)
    with pytest.raises(SystemExit):
        check_top_tier_policy.check_parallel_git_policy_execution()


def test_top_tier_policy_test_skip_execution_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "check_test_skip_policy.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "print('[TEST-SKIP-POLICY] OK')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_top_tier_policy, "TEST_SKIP_POLICY_SCRIPT", script)
    check_top_tier_policy.check_test_skip_policy_execution()


def test_top_tier_policy_test_skip_execution_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "check_test_skip_policy.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "raise SystemExit(2)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_top_tier_policy, "TEST_SKIP_POLICY_SCRIPT", script)
    with pytest.raises(SystemExit):
        check_top_tier_policy.check_test_skip_policy_execution()


def test_check_test_skip_policy_enforce_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_root = tmp_path / "tests"
    test_root.mkdir(parents=True)
    (test_root / "test_sample.py").write_text(
        "@pytest.mark.skipif(True, reason='env')\n"
        "class TestSample:\n"
        "    def test_a(self):\n"
        "        assert True\n",
        encoding="utf-8",
    )
    policy = tmp_path / "test_skip_policy.json"
    policy.write_text(
        "{\n"
        '  "schema": "warmlogic.test_skip_policy.v1",\n'
        '  "max_allowlist_entries": 1,\n'
        '  "allowlist": [\n'
        "    {\n"
        '      "path": "tests/test_sample.py",\n'
        '      "line": 1,\n'
        '      "kind": "skipif",\n'
        '      "reason": "fixture environment",\n'
        '      "expires_on": "2099-01-01"\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_test_skip_policy, "ROOT", tmp_path)
    monkeypatch.setattr(check_test_skip_policy, "TEST_ROOT", test_root)
    monkeypatch.setattr(check_test_skip_policy, "POLICY_FILE", policy)
    check_test_skip_policy.enforce()


def test_check_test_skip_policy_unallowlisted_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_root = tmp_path / "tests"
    test_root.mkdir(parents=True)
    (test_root / "test_sample.py").write_text(
        "@pytest.mark.skipif(True, reason='env')\n"
        "class TestSample:\n"
        "    def test_a(self):\n"
        "        assert True\n",
        encoding="utf-8",
    )
    policy = tmp_path / "test_skip_policy.json"
    policy.write_text(
        '{\n  "schema": "warmlogic.test_skip_policy.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_test_skip_policy, "ROOT", tmp_path)
    monkeypatch.setattr(check_test_skip_policy, "TEST_ROOT", test_root)
    monkeypatch.setattr(check_test_skip_policy, "POLICY_FILE", policy)
    with pytest.raises(SystemExit):
        check_test_skip_policy.enforce()


def test_check_test_skip_policy_expired_allowlist_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_root = tmp_path / "tests"
    test_root.mkdir(parents=True)
    (test_root / "test_sample.py").write_text(
        "@pytest.mark.skipif(True, reason='env')\n"
        "class TestSample:\n"
        "    def test_a(self):\n"
        "        assert True\n",
        encoding="utf-8",
    )
    policy = tmp_path / "test_skip_policy.json"
    policy.write_text(
        "{\n"
        '  "schema": "warmlogic.test_skip_policy.v1",\n'
        '  "max_allowlist_entries": 1,\n'
        '  "allowlist": [\n'
        "    {\n"
        '      "path": "tests/test_sample.py",\n'
        '      "line": 1,\n'
        '      "kind": "skipif",\n'
        '      "reason": "fixture environment",\n'
        '      "expires_on": "2000-01-01"\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_test_skip_policy, "ROOT", tmp_path)
    monkeypatch.setattr(check_test_skip_policy, "TEST_ROOT", test_root)
    monkeypatch.setattr(check_test_skip_policy, "POLICY_FILE", policy)
    with pytest.raises(SystemExit):
        check_test_skip_policy.enforce()


def test_check_test_skip_policy_allowlist_budget_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_root = tmp_path / "tests"
    test_root.mkdir(parents=True)
    (test_root / "test_sample.py").write_text(
        "@pytest.mark.skipif(True, reason='env')\n"
        "class TestSample:\n"
        "    def test_a(self):\n"
        "        assert True\n",
        encoding="utf-8",
    )
    policy = tmp_path / "test_skip_policy.json"
    policy.write_text(
        "{\n"
        '  "schema": "warmlogic.test_skip_policy.v1",\n'
        '  "max_allowlist_entries": 0,\n'
        '  "allowlist": [\n'
        "    {\n"
        '      "path": "tests/test_sample.py",\n'
        '      "line": 1,\n'
        '      "kind": "skipif",\n'
        '      "reason": "fixture environment",\n'
        '      "expires_on": "2099-01-01"\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_test_skip_policy, "ROOT", tmp_path)
    monkeypatch.setattr(check_test_skip_policy, "TEST_ROOT", test_root)
    monkeypatch.setattr(check_test_skip_policy, "POLICY_FILE", policy)
    with pytest.raises(SystemExit):
        check_test_skip_policy.enforce()


def test_parallel_git_policy_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n  - run: bash scripts/ops/git_mutex.sh -- git add foo\n", encoding="utf-8"
    )
    (workflow_root / "compat-accept.yml").write_text(
        "steps:\n"
        "  - run: |\n"
        "      git add -A\n"
        "      git commit -m 'compat'\n"
        "      git push\n",
        encoding="utf-8",
    )

    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        "{\n"
        '  "schema": "warmlogic.parallel_git_exceptions.v1",\n'
        '  "max_allowlist_entries": 1,\n'
        '  "allowlist": [\n'
        "    {\n"
        '      "path": ".github/workflows/compat-accept.yml",\n'
        '      "reason": "legacy compat acceptance path",\n'
        f'      "expires_on": "{_future_expiry()}"\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_missing_runbook_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text("missing required snippets\n", encoding="utf-8")

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n  - run: bash scripts/ops/git_mutex.sh -- git add foo\n", encoding="utf-8"
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    with pytest.raises(SystemExit):
        check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_direct_git_workflow_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n  - run: |\n      git add -A\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    with pytest.raises(SystemExit):
        check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_stale_allowlist_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "compat-accept.yml").write_text(
        "steps:\n  - run: bash scripts/ops/git_mutex.sh -- git add foo\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        "{\n"
        '  "schema": "warmlogic.parallel_git_exceptions.v1",\n'
        '  "max_allowlist_entries": 1,\n'
        '  "allowlist": [\n'
        "    {\n"
        '      "path": ".github/workflows/compat-accept.yml",\n'
        '      "reason": "legacy compat acceptance path",\n'
        f'      "expires_on": "{_future_expiry()}"\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    with pytest.raises(SystemExit):
        check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_expired_allowlist_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "compat-accept.yml").write_text(
        "steps:\n"
        "  - run: |\n"
        "      git add -A\n"
        "      git commit -m 'compat'\n"
        "      git push\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        "{\n"
        '  "schema": "warmlogic.parallel_git_exceptions.v1",\n'
        '  "max_allowlist_entries": 1,\n'
        '  "allowlist": [\n'
        "    {\n"
        '      "path": ".github/workflows/compat-accept.yml",\n'
        '      "reason": "legacy compat acceptance path",\n'
        '      "expires_on": "2000-01-01"\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    with pytest.raises(SystemExit):
        check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_allowlist_budget_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        "{\n"
        '  "schema": "warmlogic.parallel_git_exceptions.v1",\n'
        '  "max_allowlist_entries": 0,\n'
        '  "allowlist": [\n'
        "    {\n"
        '      "path": ".github/workflows/compat-accept.yml",\n'
        '      "reason": "temporary exception",\n'
        '      "expires_on": "2099-01-01"\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)
    with pytest.raises(SystemExit):
        check_parallel_git_ops.load_exception_allowlist()


def test_parallel_git_policy_detects_inline_mutating_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n  - run: if [ -n \"x\" ]; then git add -A; fi\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    with pytest.raises(SystemExit):
        check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_allows_inline_mutex_wrapped_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n  - run: if [ -n \"x\" ]; then bash scripts/ops/git_mutex.sh -- git add -A; fi\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_ignores_echoed_git_strings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n  - run: echo \"git add -A\"\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_detects_git_with_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n  - run: if [ -n \"x\" ]; then git -C . add -A; fi\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    with pytest.raises(SystemExit):
        check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_allows_mutex_wrapped_git_with_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n  - run: if [ -n \"x\" ]; then bash scripts/ops/git_mutex.sh -- git -C . add -A; fi\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_detects_backslash_continuation_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n"
        "  - run: |\n"
        "      if [ -n \"x\" ]; then git -C . \\\n"
        "        add -A; fi\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    with pytest.raises(SystemExit):
        check_parallel_git_ops.check_parallel_git_ops_policy()


def test_parallel_git_policy_allows_backslash_continuation_mutex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutex = tmp_path / "git_mutex.sh"
    mutex.write_text(
        "#!/usr/bin/env bash\n"
        "LOCK_OWNER=owner\n"
        "STALE_SECONDS=10\n"
        "wait_for_index_lock_clear(){ :; }\n"
        "run_with_index_lock_retries(){ :; }\n"
        "echo 'index.lock race detected'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_mutex.sh'; exit 0; fi\n",
        encoding="utf-8",
    )
    mutex.chmod(0o755)

    safe_commit = tmp_path / "git_safe_commit.sh"
    safe_commit.write_text(
        "#!/usr/bin/env bash\n"
        "MUTEX=x\n"
        "paths=(a)\n"
        "echo 'path not found'\n"
        "echo 'git add -- \"${paths[@]}\"'\n"
        "echo 'git commit -m \"$MESSAGE\" -- \"${paths[@]}\"'\n"
        "echo 'bash \"$MUTEX\"'\n"
        "if [[ \"${1:-}\" == \"--help\" ]]; then echo 'Usage: git_safe_commit.sh --message \"P4xx\"'; exit 0; fi\n",
        encoding="utf-8",
    )
    safe_commit.chmod(0o755)

    runbook = tmp_path / "PARALLEL_GIT_OPERATIONS.md"
    runbook.write_text(
        "scripts/ops/git_mutex.sh\n"
        "scripts/ops/git_safe_commit.sh\n"
        ".git/index.lock\n"
        "config/security/parallel_git_exceptions.json\n"
        "max_allowlist_entries\n",
        encoding="utf-8",
    )

    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci-main.yml").write_text(
        "steps:\n"
        "  - run: |\n"
        "      if [ -n \"x\" ]; then bash scripts/ops/git_mutex.sh -- git -C . \\\n"
        "        add -A; fi\n",
        encoding="utf-8",
    )
    exceptions = tmp_path / "parallel_git_exceptions.json"
    exceptions.write_text(
        '{\n  "schema": "warmlogic.parallel_git_exceptions.v1",\n  "max_allowlist_entries": 0,\n  "allowlist": []\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_parallel_git_ops, "GIT_MUTEX_SCRIPT", mutex)
    monkeypatch.setattr(check_parallel_git_ops, "GIT_SAFE_COMMIT_SCRIPT", safe_commit)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_RUNBOOK", runbook)
    monkeypatch.setattr(check_parallel_git_ops, "WORKFLOW_ROOT", workflow_root)
    monkeypatch.setattr(check_parallel_git_ops, "PARALLEL_GIT_EXCEPTIONS", exceptions)

    check_parallel_git_ops.check_parallel_git_ops_policy()
