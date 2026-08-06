#!/usr/bin/env python3
"""Fail CI when workflow soft-gate debt exceeds agreed budget."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUDGET_FILE = ROOT / "config" / "security" / "ci_soft_gate_budget.json"
RG_PATTERN = r"\|\| true|continue-on-error:\s*true|--exit-zero"


def fail(msg: str) -> None:
    print(f"[SOFT-GATE-BUDGET] ERROR: {msg}")
    sys.exit(1)


def load_budget() -> dict:
    if not BUDGET_FILE.exists():
        fail(f"missing budget file: {BUDGET_FILE}")
    with BUDGET_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def collect_hits() -> list[str]:
    if shutil.which("rg") is None:
        pattern = re.compile(RG_PATTERN)
        hits: list[str] = []
        workflows_root = ROOT / ".github" / "workflows"
        for path in sorted(workflows_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if pattern.search(line):
                    hits.append(f"{rel}:{lineno}:{line}")
        return hits

    proc = subprocess.run(
        ["rg", "-n", RG_PATTERN, ".github/workflows"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        fail(f"rg failed with code {proc.returncode}: {proc.stderr.strip()}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def classify(lines: list[str]) -> dict[str, int]:
    counts = {"|| true": 0, "continue-on-error: true": 0, "--exit-zero": 0}
    for line in lines:
        if "|| true" in line:
            counts["|| true"] += 1
        if "continue-on-error: true" in line:
            counts["continue-on-error: true"] += 1
        if "--exit-zero" in line:
            counts["--exit-zero"] += 1
    return counts


def enforce_allowlist(lines: list[str], budget: dict) -> None:
    allow = budget.get("allowlist", {})
    allowed_continue_files = set(allow.get("continue-on-error: true", []))
    if not allowed_continue_files:
        return

    offenders = []
    for line in lines:
        if "continue-on-error: true" not in line:
            continue
        file_path = line.split(":", 1)[0]
        if file_path not in allowed_continue_files:
            offenders.append(line)

    if offenders:
        fail(
            "continue-on-error used outside allowlist.\n"
            + "\n".join(offenders[:20])
        )


def main() -> None:
    budget = load_budget()
    lines = collect_hits()
    observed_total = len(lines)
    observed = classify(lines)

    max_total = int(budget["max_total"])
    max_by_pattern = {k: int(v) for k, v in budget["max_by_pattern"].items()}

    violations = []
    if observed_total > max_total:
        violations.append(f"total {observed_total} > budget {max_total}")
    for key, max_v in max_by_pattern.items():
        if observed.get(key, 0) > max_v:
            violations.append(f"{key}: {observed.get(key, 0)} > budget {max_v}")

    print(
        "[SOFT-GATE-BUDGET] observed:",
        f"total={observed_total}",
        ", ".join(f"{k}={v}" for k, v in observed.items()),
    )

    if violations:
        preview = "\n".join(lines[:20])
        fail(" ; ".join(violations) + f"\nTop matches:\n{preview}")

    enforce_allowlist(lines, budget)

    print("[SOFT-GATE-BUDGET] OK: soft-gate debt did not increase")


if __name__ == "__main__":
    main()
