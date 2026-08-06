# CI Evidence Gates Runbook

## Goal
Provide deterministic evidence artifacts for critical CI workflows and show how to verify them locally.

## Evidence Artifacts
- `ci-main-evidence` -> `artifacts/ci-evidence/ci-main.json`
- `ci-security-evidence` -> `artifacts/ci-evidence/ci-security.json`
- `ci-production-gate-evidence` -> `artifacts/ci-evidence/ci-production-gate.json`

All payloads use schema: `warmlogic.ci.evidence.v1`.

## Local Schema/Writer Check
```bash
python scripts/ci/write_ci_evidence.py \
  --out /tmp/ci-main.json \
  --gate ci-main \
  --workflow "CI Main" \
  --run-id local \
  --run-attempt 1 \
  --event-name workflow_dispatch \
  --ref refs/heads/local \
  --sha local \
  --job-status pass \
  --job-result "lint=success" \
  --job-result "test-python=success"

python scripts/ci/validate_ci_evidence.py \
  --input /tmp/ci-main.json \
  --contract config/security/ci_evidence_contract.json
```

Expected:
- Command exits `0`
- `/tmp/ci-main.json` exists
- `schema` field equals `warmlogic.ci.evidence.v1`
- Validator prints `[CI-EVIDENCE-VALIDATE] OK ...`

## Local Policy Gate Check
```bash
python scripts/ci/check_top_tier_policy.py
```

Expected:
- `[TOP-TIER-POLICY] OK: strict workflow policy guards passed`

This verifies evidence wiring exists in:
- `.github/workflows/ci-main.yml`
- `.github/workflows/ci-security.yml`
- `.github/workflows/ci-production-gate.yml`
- Parallel git mutation policy is executable (`scripts/ci/check_parallel_git_ops.py`)
- Test skip/xfail allowlist policy is executable (`scripts/ci/check_test_skip_policy.py`)

## Local One-Command Gate Runner
```bash
# Fast path (policy + target e2e)
make ci-top-tier-local-fast

# Full path (includes strict full suite)
make ci-top-tier-local
```

Both commands execute through:
- `scripts/ci/run_local_top_tier_gate.sh`
- Full mode enforces JUnit strict summary gate (`skipped=0`, `failures=0`, `errors=0`) via:
  - `scripts/ci/check_junit_summary.py`

## Optional GitHub Artifact Retrieval
When GitHub execution is used, artifacts can be pulled with:
```bash
gh run list --workflow "CI Main" --limit 1
gh run download <run-id> --name ci-main-evidence --dir /tmp/ci-artifacts
cat /tmp/ci-artifacts/ci-main.json
```

Repeat with:
- workflow `Security`, artifact `ci-security-evidence`
- workflow `CI Production Gate`, artifact `ci-production-gate-evidence`
