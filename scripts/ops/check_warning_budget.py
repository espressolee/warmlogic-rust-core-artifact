#!/usr/bin/env python3
"""Check pytest warning budget from a captured pytest log."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Tuple


WARNING_TYPE_RE = re.compile(r":\s([A-Za-z_][A-Za-z0-9_]*):")
GROUP_COUNT_RE = re.compile(r"^.+:\s(\d+)\swarnings$")
TOTAL_WARNINGS_RE = re.compile(r"=\s+\d+\spassed,.*,\s(\d+)\swarnings\sin\s")
NODEID_RE = re.compile(r"^[A-Za-z0-9_./-]+::")


def _parse_warning_type(line: str) -> str | None:
    match = WARNING_TYPE_RE.search(line)
    if match:
        return match.group(1)
    return None


def parse_pytest_warning_summary(log_text: str) -> Tuple[int, Counter]:
    lines = log_text.splitlines()
    total_warnings = 0

    for line in lines:
        total_match = TOTAL_WARNINGS_RE.search(line)
        if total_match:
            total_warnings = int(total_match.group(1))

    type_counts: Counter = Counter()
    in_warning_summary = False
    index = 0

    while index < len(lines):
        line = lines[index]
        if "warnings summary" in line:
            in_warning_summary = True
            index += 1
            continue
        if in_warning_summary and line.startswith("-- Docs:"):
            break
        if not in_warning_summary:
            index += 1
            continue

        group_match = GROUP_COUNT_RE.match(line)
        if group_match:
            count = int(group_match.group(1))
            detail_index = index + 1
            while detail_index < len(lines) and not lines[detail_index].strip():
                detail_index += 1
            warning_type = (
                _parse_warning_type(lines[detail_index])
                if detail_index < len(lines)
                else None
            )
            if warning_type:
                type_counts[warning_type] += count
            index = detail_index + 1
            continue

        if NODEID_RE.match(line):
            node_count = 1
            detail_index = index + 1
            while detail_index < len(lines) and NODEID_RE.match(lines[detail_index]):
                node_count += 1
                detail_index += 1
            warning_type = (
                _parse_warning_type(lines[detail_index])
                if detail_index < len(lines)
                else None
            )
            if warning_type:
                type_counts[warning_type] += node_count
            index = detail_index + 1
            continue

        index += 1

    accounted = sum(type_counts.values())
    if total_warnings > accounted:
        type_counts["_UNCLASSIFIED"] += total_warnings - accounted

    return total_warnings, type_counts


def load_budget(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_budget(total: int, counts: Counter, budget: Dict[str, object]) -> Tuple[bool, str]:
    max_total = int(budget.get("max_total_warnings", 0))
    max_unknown = int(budget.get("max_unknown_warning_types", 0))
    by_type: Dict[str, int] = {
        str(key): int(value) for key, value in dict(budget.get("max_by_type", {})).items()
    }

    failures = []
    if total > max_total:
        failures.append(f"total warnings {total} > budget {max_total}")

    for warning_type, count in sorted(counts.items()):
        if warning_type == "_UNCLASSIFIED":
            if count > max_unknown:
                failures.append(f"unclassified warnings {count} > budget {max_unknown}")
            continue
        allowed = by_type.get(warning_type)
        if allowed is None:
            if count > max_unknown:
                failures.append(
                    f"unexpected warning type {warning_type}={count} exceeds unknown budget {max_unknown}"
                )
            continue
        if count > allowed:
            failures.append(f"{warning_type}={count} > budget {allowed}")

    summary_lines = [f"total={total}", "by_type:"]
    for warning_type, count in sorted(counts.items()):
        summary_lines.append(f"  - {warning_type}: {count}")
    summary = "\n".join(summary_lines)

    if failures:
        return False, f"{summary}\nBUDGET FAIL:\n  - " + "\n  - ".join(failures)
    return True, f"{summary}\nBUDGET PASS"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pytest warning budget")
    parser.add_argument("--log", required=True, help="Path to pytest output log")
    parser.add_argument("--budget", required=True, help="Path to warning budget JSON")
    args = parser.parse_args()

    log_path = Path(args.log)
    budget_path = Path(args.budget)

    if not log_path.exists():
        print(f"[error] log not found: {log_path}", file=sys.stderr)
        return 2
    if not budget_path.exists():
        print(f"[error] budget not found: {budget_path}", file=sys.stderr)
        return 2

    text = log_path.read_text(encoding="utf-8", errors="ignore")
    total, counts = parse_pytest_warning_summary(text)
    budget = load_budget(budget_path)
    ok, report = check_budget(total, counts, budget)
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
