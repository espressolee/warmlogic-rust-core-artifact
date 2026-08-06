#!/usr/bin/env python3
"""Enforce strict CI policy on top-tier critical workflows."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CRITICAL_WORKFLOWS = [
    ROOT / ".github" / "workflows" / "ci-main.yml",
    ROOT / ".github" / "workflows" / "ci-security.yml",
    ROOT / ".github" / "workflows" / "ci-production-gate.yml",
]
CODECOV = ROOT / "codecov.yml"
RELEASE_ON_TAG = ROOT / ".github" / "workflows" / "release-on-tag.yml"
CI_MAIN = ROOT / ".github" / "workflows" / "ci-main.yml"
CI_SECURITY = ROOT / ".github" / "workflows" / "ci-security.yml"
CI_PRODUCTION_GATE = ROOT / ".github" / "workflows" / "ci-production-gate.yml"
MAKEFILE = ROOT / "Makefile"
CI_EVIDENCE_RUNBOOK = ROOT / "docs" / "runbooks" / "ci-evidence-gates.md"
COVERAGE_RATCHET_CONFIG = ROOT / "config" / "security" / "coverage_ratchet.json"
DIGEST_REFRESH_WORKFLOW = ROOT / ".github" / "workflows" / "ci-docker-digest-refresh.yml"
CI_EVIDENCE_SCRIPT = ROOT / "scripts" / "ci" / "write_ci_evidence.py"
CI_EVIDENCE_VALIDATOR_SCRIPT = ROOT / "scripts" / "ci" / "validate_ci_evidence.py"
CI_EVIDENCE_CONTRACT = ROOT / "config" / "security" / "ci_evidence_contract.json"
LOCAL_TOP_TIER_GATE_SCRIPT = ROOT / "scripts" / "ci" / "run_local_top_tier_gate.sh"
JUNIT_SUMMARY_SCRIPT = ROOT / "scripts" / "ci" / "check_junit_summary.py"
PARALLEL_GIT_POLICY_SCRIPT = ROOT / "scripts" / "ci" / "check_parallel_git_ops.py"
PARALLEL_GIT_RUNBOOK = ROOT / "docs" / "dev" / "PARALLEL_GIT_OPERATIONS.md"
TEST_SKIP_POLICY_SCRIPT = ROOT / "scripts" / "ci" / "check_test_skip_policy.py"

FORBIDDEN = [
    re.compile(r"\|\|\s*true"),
    re.compile(r"continue-on-error:\s*true"),
    re.compile(r"--exit-zero"),
]


def fail(msg: str) -> None:
    print(f"[TOP-TIER-POLICY] ERROR: {msg}")
    sys.exit(1)


def read_text(path: Path) -> str:
    if not path.exists():
        fail(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def check_no_soft_gates(path: Path, content: str) -> None:
    for pattern in FORBIDDEN:
        m = pattern.search(content)
        if m:
            fail(f"forbidden soft-gate pattern '{pattern.pattern}' found in {path}")


def check_codecov_policy() -> None:
    content = read_text(CODECOV)
    if "require_ci_to_pass: true" not in content:
        fail("codecov.yml must set require_ci_to_pass: true")
    if re.search(r"informational:\s*true", content):
        fail("codecov.yml must not use informational: true for coverage status")


def check_security_workflow() -> None:
    path = ROOT / ".github" / "workflows" / "ci-security.yml"
    content = read_text(path)
    for needle in (
        "pip-audit",
        "cargo deny check",
        "python scripts/ci/check_parallel_git_ops.py",
        "python scripts/ci/check_test_skip_policy.py",
    ):
        if needle not in content:
            fail(f"{path} missing required security gate: {needle}")


def check_production_gate_workflow() -> None:
    path = ROOT / ".github" / "workflows" / "ci-production-gate.yml"
    content = read_text(path)
    required_snippets = [
        "python scripts/ci/check_parallel_git_ops.py",
        "python scripts/ci/check_test_skip_policy.py",
        "WARM_RUN_MESH_E2E=1 pytest -q -W error -ra tests/e2e/test_mesh_sync.py::test_gossip_propagation",
        "WARM_UI_BASE_URL=http://127.0.0.1:8011 pytest -q -W error -ra tests/security/test_constitutional_e2e.py::TestConstitutionalE2E::test_e2e_api_guard",
        "WARM_RUN_MESH_E2E=1 WARM_UI_BASE_URL=http://127.0.0.1:8011 pytest -n auto -q -W error -ra",
        "--junitxml /tmp/warmlogic_strict_full.junit.xml",
        "python scripts/ci/check_junit_summary.py",
        "--max-skipped 0",
    ]
    for snippet in required_snippets:
        if snippet not in content:
            fail(f"{path} missing required strict gate command: {snippet}")


def check_release_provenance_policy() -> None:
    content = read_text(RELEASE_ON_TAG)
    required = [
        "attestations: write",
        "id-token: write",
        "actions/attest-build-provenance@v2",
        "CHECKSUMS_SHA256.txt",
        "sha256sum *.whl sbom_packages.json > CHECKSUMS_SHA256.txt",
    ]
    for needle in required:
        if needle not in content:
            fail(f"{RELEASE_ON_TAG} missing release trust control: {needle}")


def check_coverage_ratchet_policy() -> None:
    content = read_text(CI_MAIN)
    required_main_snippets = [
        "python scripts/ci/check_parallel_git_ops.py",
        "python scripts/ci/check_test_skip_policy.py",
        "--cov-report=json",
        "python scripts/ci/check_coverage_ratchet.py",
    ]
    for snippet in required_main_snippets:
        if snippet not in content:
            fail(f"{CI_MAIN} missing coverage ratchet requirement: {snippet}")

    if not COVERAGE_RATCHET_CONFIG.exists():
        fail(f"missing coverage ratchet config: {COVERAGE_RATCHET_CONFIG}")
    with COVERAGE_RATCHET_CONFIG.open("r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    baseline = cfg.get("minimum_total_percent")
    try:
        baseline = float(baseline)
    except (TypeError, ValueError):
        fail(
            f"{COVERAGE_RATCHET_CONFIG} has invalid minimum_total_percent: "
            f"{baseline!r}"
        )
    if baseline < 0:
        fail(f"{COVERAGE_RATCHET_CONFIG} minimum_total_percent must be >= 0")


def check_digest_refresh_policy() -> None:
    content = read_text(DIGEST_REFRESH_WORKFLOW)
    required = [
        "schedule:",
        "scripts/ci/update_python_base_digest.py",
        "peter-evans/create-pull-request@v6",
    ]
    for needle in required:
        if needle not in content:
            fail(f"{DIGEST_REFRESH_WORKFLOW} missing digest refresh control: {needle}")


def check_ci_evidence_policy() -> None:
    if not CI_EVIDENCE_SCRIPT.exists():
        fail(f"missing CI evidence writer script: {CI_EVIDENCE_SCRIPT}")
    if not CI_EVIDENCE_VALIDATOR_SCRIPT.exists():
        fail(f"missing CI evidence validator script: {CI_EVIDENCE_VALIDATOR_SCRIPT}")
    if not CI_EVIDENCE_CONTRACT.exists():
        fail(f"missing CI evidence contract file: {CI_EVIDENCE_CONTRACT}")

    main_content = read_text(CI_MAIN)
    main_required = [
        "scripts/ci/write_ci_evidence.py",
        "scripts/ci/validate_ci_evidence.py",
        "--gate ci-main",
        "--input artifacts/ci-evidence/ci-main.json",
        "name: ci-main-evidence",
    ]
    for needle in main_required:
        if needle not in main_content:
            fail(f"{CI_MAIN} missing CI evidence control: {needle}")

    security_content = read_text(CI_SECURITY)
    security_required = [
        "scripts/ci/write_ci_evidence.py",
        "scripts/ci/validate_ci_evidence.py",
        "--gate ci-security",
        "--input artifacts/ci-evidence/ci-security.json",
        "name: ci-security-evidence",
    ]
    for needle in security_required:
        if needle not in security_content:
            fail(f"{CI_SECURITY} missing CI evidence control: {needle}")

    prod_content = read_text(CI_PRODUCTION_GATE)
    prod_required = [
        "name: Write CI evidence (production gate)",
        "if: always()",
        "scripts/ci/write_ci_evidence.py",
        "scripts/ci/validate_ci_evidence.py",
        "--gate ci-production-gate",
        "--input artifacts/ci-evidence/ci-production-gate.json",
        "name: ci-production-gate-evidence",
    ]
    for needle in prod_required:
        if needle not in prod_content:
            fail(f"{CI_PRODUCTION_GATE} missing CI evidence control: {needle}")


def check_local_gate_repro_policy() -> None:
    if not LOCAL_TOP_TIER_GATE_SCRIPT.exists():
        fail(f"missing local top-tier gate runner: {LOCAL_TOP_TIER_GATE_SCRIPT}")
    if not JUNIT_SUMMARY_SCRIPT.exists():
        fail(f"missing junit summary gate script: {JUNIT_SUMMARY_SCRIPT}")
    if not PARALLEL_GIT_POLICY_SCRIPT.exists():
        fail(f"missing parallel git policy gate script: {PARALLEL_GIT_POLICY_SCRIPT}")
    if not PARALLEL_GIT_RUNBOOK.exists():
        fail(f"missing parallel git operations runbook: {PARALLEL_GIT_RUNBOOK}")

    make_content = read_text(MAKEFILE)
    for target in ("ci-top-tier-policy:", "ci-top-tier-local-fast:", "ci-top-tier-local:"):
        if target not in make_content:
            fail(f"{MAKEFILE} missing required local gate target: {target}")

    runbook_content = read_text(CI_EVIDENCE_RUNBOOK)
    for cmd in ("make ci-top-tier-local-fast", "make ci-top-tier-local"):
        if cmd not in runbook_content:
            fail(f"{CI_EVIDENCE_RUNBOOK} missing local gate command: {cmd}")

    local_gate = read_text(LOCAL_TOP_TIER_GATE_SCRIPT)
    for snippet in (
        "scripts/ci/check_junit_summary.py",
        "--max-skipped 0",
        "scripts/ci/check_parallel_git_ops.py",
    ):
        if snippet not in local_gate:
            fail(
                f"{LOCAL_TOP_TIER_GATE_SCRIPT} missing strict junit skip gate: {snippet}"
            )


def check_parallel_git_policy_execution() -> None:
    if not PARALLEL_GIT_POLICY_SCRIPT.exists():
        fail(f"missing parallel git policy gate script: {PARALLEL_GIT_POLICY_SCRIPT}")

    try:
        proc = subprocess.run(
            [sys.executable, str(PARALLEL_GIT_POLICY_SCRIPT)],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as e:
        fail(f"failed to execute parallel git policy gate: {e}")

    if proc.returncode != 0:
        output = f"{proc.stdout}\n{proc.stderr}".strip()
        detail = f"\n{output}" if output else ""
        fail(
            "parallel git policy gate failed "
            f"(exit {proc.returncode}): {PARALLEL_GIT_POLICY_SCRIPT}{detail}"
        )


def check_test_skip_policy_execution() -> None:
    if not TEST_SKIP_POLICY_SCRIPT.exists():
        fail(f"missing test skip policy gate script: {TEST_SKIP_POLICY_SCRIPT}")

    try:
        proc = subprocess.run(
            [sys.executable, str(TEST_SKIP_POLICY_SCRIPT)],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as e:
        fail(f"failed to execute test skip policy gate: {e}")

    if proc.returncode != 0:
        output = f"{proc.stdout}\n{proc.stderr}".strip()
        detail = f"\n{output}" if output else ""
        fail(
            "test skip policy gate failed "
            f"(exit {proc.returncode}): {TEST_SKIP_POLICY_SCRIPT}{detail}"
        )


def main() -> None:
    for wf in CRITICAL_WORKFLOWS:
        content = read_text(wf)
        check_no_soft_gates(wf, content)

    check_codecov_policy()
    check_security_workflow()
    check_production_gate_workflow()
    check_release_provenance_policy()
    check_coverage_ratchet_policy()
    check_digest_refresh_policy()
    check_ci_evidence_policy()
    check_local_gate_repro_policy()
    check_parallel_git_policy_execution()
    check_test_skip_policy_execution()
    print("[TOP-TIER-POLICY] OK: strict workflow policy guards passed")


if __name__ == "__main__":
    main()
