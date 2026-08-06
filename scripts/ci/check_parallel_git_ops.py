#!/usr/bin/env python3
"""Validate parallel Git operation guardrails for multi-agent environments."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GIT_MUTEX_SCRIPT = ROOT / "scripts" / "ops" / "git_mutex.sh"
GIT_SAFE_COMMIT_SCRIPT = ROOT / "scripts" / "ops" / "git_safe_commit.sh"
PARALLEL_GIT_RUNBOOK = ROOT / "docs" / "dev" / "PARALLEL_GIT_OPERATIONS.md"
PARALLEL_GIT_EXCEPTIONS = (
    ROOT / "config" / "security" / "parallel_git_exceptions.json"
)
WORKFLOW_ROOT = ROOT / ".github" / "workflows"

GIT_OPTION_SEGMENT = r"(?:\s+-[^\s]+(?:\s+[^\s;|&]+)?)"
GIT_OPTION_BLOCK = rf"(?:{GIT_OPTION_SEGMENT})*"
MUTATING_GIT_CMD = re.compile(
    rf"(?:^\s*|[;&|]\s*|\bthen\s+|\bdo\s+)git{GIT_OPTION_BLOCK}\s+(add|commit|push)\b"
)
SAFE_MUTEX_CMD = re.compile(
    r"(?:^\s*|[;&|]\s*|\bthen\s+|\bdo\s+)"
    rf"(?:bash\s+)?(?:\./)?scripts/ops/git_mutex\.sh\s+--\s+git{GIT_OPTION_BLOCK}\s+(add|commit|push)\b"
)
SAFE_COMMIT_CMD = re.compile(
    r"(?:^\s*|[;&|]\s*|\bthen\s+|\bdo\s+)"
    r"(?:bash\s+)?(?:\./)?scripts/ops/git_safe_commit\.sh\b"
)


def fail(msg: str) -> None:
    print(f"[PARALLEL-GIT-POLICY] ERROR: {msg}")
    raise SystemExit(1)


def require_path(path: Path, *, executable: bool = False) -> None:
    if not path.exists():
        fail(f"missing required file: {path}")
    if executable and not os.access(path, os.X_OK):
        fail(f"script must be executable: {path}")


def ensure_help_contains(path: Path, snippets: list[str]) -> None:
    try:
        proc = subprocess.run(
            ["bash", str(path), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as e:
        fail(f"failed to execute {path} --help: {e}")

    if proc.returncode != 0:
        fail(f"{path} --help failed with exit code {proc.returncode}")
    output = f"{proc.stdout}\n{proc.stderr}"
    for snippet in snippets:
        if snippet not in output:
            fail(f"{path} --help missing required snippet: {snippet!r}")


def ensure_script_contains(path: Path, snippets: list[str]) -> None:
    content = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in content:
            fail(f"{path} missing required implementation guard: {snippet!r}")


def load_exception_allowlist() -> dict[str, dict[str, str]]:
    require_path(PARALLEL_GIT_EXCEPTIONS)
    try:
        payload = json.loads(PARALLEL_GIT_EXCEPTIONS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{PARALLEL_GIT_EXCEPTIONS} has invalid JSON: {e}")

    if payload.get("schema") != "warmlogic.parallel_git_exceptions.v1":
        fail(
            f"{PARALLEL_GIT_EXCEPTIONS} has invalid schema: "
            f"{payload.get('schema')!r}"
        )

    allowlist = payload.get("allowlist")
    if not isinstance(allowlist, list):
        fail(f"{PARALLEL_GIT_EXCEPTIONS} allowlist must be a list")
    max_entries = payload.get("max_allowlist_entries")
    if not isinstance(max_entries, int) or max_entries < 0:
        fail(f"{PARALLEL_GIT_EXCEPTIONS} max_allowlist_entries must be >= 0 integer")
    if len(allowlist) > max_entries:
        fail(
            f"{PARALLEL_GIT_EXCEPTIONS} allowlist exceeds budget: "
            f"{len(allowlist)} > {max_entries}"
        )

    normalized: dict[str, dict[str, str]] = {}
    today = date.today()
    for item in allowlist:
        if not isinstance(item, dict):
            fail(f"{PARALLEL_GIT_EXCEPTIONS} allowlist entries must be objects")
        path = item.get("path")
        reason = item.get("reason")
        expires_on = item.get("expires_on")
        if not isinstance(path, str) or not path:
            fail(f"{PARALLEL_GIT_EXCEPTIONS} allowlist entry missing path")
        if not isinstance(reason, str) or not reason:
            fail(
                f"{PARALLEL_GIT_EXCEPTIONS} allowlist entry {path!r} missing reason"
            )
        if not isinstance(expires_on, str) or not expires_on:
            fail(
                f"{PARALLEL_GIT_EXCEPTIONS} allowlist entry {path!r} missing "
                "expires_on"
            )
        try:
            expires_date = date.fromisoformat(expires_on)
        except ValueError:
            fail(
                f"{PARALLEL_GIT_EXCEPTIONS} allowlist entry {path!r} has invalid "
                f"expires_on (expected YYYY-MM-DD): {expires_on!r}"
            )
        if expires_date < today:
            fail(
                f"{PARALLEL_GIT_EXCEPTIONS} allowlist entry {path!r} expired on "
                f"{expires_on}; remove or migrate to mutex-safe git path"
            )
        normalized[path] = {"reason": reason, "expires_on": expires_on}
    return normalized


def check_workflow_mutating_git_commands() -> None:
    require_path(WORKFLOW_ROOT)
    allowlist = load_exception_allowlist()
    allowed_hits: set[str] = set()
    violations: list[str] = []

    for workflow in sorted(WORKFLOW_ROOT.glob("*.yml")):
        rel = (Path(".github") / "workflows" / workflow.name).as_posix()
        is_allowlisted = rel in allowlist
        lines = workflow.read_text(encoding="utf-8").splitlines()
        idx = 0
        while idx < len(lines):
            lineno = idx + 1
            stripped = lines[idx].strip()
            logical = stripped

            # Join shell backslash continuations to avoid missing split git commands.
            while logical.endswith("\\") and (idx + 1) < len(lines):
                logical = logical[:-1].rstrip() + " " + lines[idx + 1].strip()
                idx += 1

            idx += 1
            if not logical or logical.startswith("#"):
                continue
            if SAFE_MUTEX_CMD.search(logical) or SAFE_COMMIT_CMD.search(logical):
                continue
            if MUTATING_GIT_CMD.search(logical):
                if is_allowlisted:
                    allowed_hits.add(rel)
                    continue
                violations.append(f"{rel}:{lineno}: {logical}")

    stale_allowlist = sorted(set(allowlist) - allowed_hits)
    if stale_allowlist:
        fail(
            "parallel git allowlist contains stale entries with no matching direct "
            f"git mutation commands: {', '.join(stale_allowlist)}"
        )

    if violations:
        fail(
            "direct git mutation in workflows must use scripts/ops/git_mutex.sh "
            "or scripts/ops/git_safe_commit.sh. Violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


def check_runbook_content() -> None:
    content = PARALLEL_GIT_RUNBOOK.read_text(encoding="utf-8")
    required_snippets = [
        "scripts/ops/git_mutex.sh",
        "scripts/ops/git_safe_commit.sh",
        ".git/index.lock",
        "config/security/parallel_git_exceptions.json",
        "max_allowlist_entries",
    ]
    for snippet in required_snippets:
        if snippet not in content:
            fail(f"{PARALLEL_GIT_RUNBOOK} missing required guidance: {snippet!r}")


def check_parallel_git_ops_policy() -> None:
    require_path(GIT_MUTEX_SCRIPT, executable=True)
    require_path(GIT_SAFE_COMMIT_SCRIPT, executable=True)
    require_path(PARALLEL_GIT_RUNBOOK)
    ensure_help_contains(GIT_MUTEX_SCRIPT, ["Usage:", "git_mutex.sh"])
    ensure_help_contains(GIT_SAFE_COMMIT_SCRIPT, ["Usage:", "git_safe_commit.sh"])
    ensure_script_contains(
        GIT_MUTEX_SCRIPT,
        [
            "LOCK_OWNER=",
            "STALE_SECONDS=",
            "wait_for_index_lock_clear",
            "run_with_index_lock_retries",
            "index.lock race detected",
        ],
    )
    ensure_script_contains(
        GIT_SAFE_COMMIT_SCRIPT,
        [
            "git add -- \"${paths[@]}\"",
            "git commit -m \"$MESSAGE\" -- \"${paths[@]}\"",
            "path not found",
            "bash \"$MUTEX\"",
        ],
    )
    check_runbook_content()
    check_workflow_mutating_git_commands()


def main() -> None:
    check_parallel_git_ops_policy()
    print("[PARALLEL-GIT-POLICY] OK: parallel git operation controls are in place")


if __name__ == "__main__":
    main()
