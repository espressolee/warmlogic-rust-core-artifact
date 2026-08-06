#!/usr/bin/env python3
"""Validate pytest JUnit summary counts against strict limits."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def fail(msg: str) -> None:
    print(f"[JUNIT-SUMMARY] ERROR: {msg}")
    sys.exit(1)


def parse_junit(path: Path) -> dict[str, int]:
    if not path.exists():
        fail(f"missing junit file: {path}")
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        fail(f"invalid junit xml ({path}): {exc}")

    root = tree.getroot()
    suites: list[ET.Element]
    if root.tag == "testsuites":
        suites = [node for node in root if node.tag == "testsuite"]
    elif root.tag == "testsuite":
        suites = [root]
    else:
        fail(f"unsupported root tag: {root.tag!r}")
        raise AssertionError("unreachable")

    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            raw = suite.attrib.get(key, "0")
            try:
                value = int(float(raw))
            except (TypeError, ValueError):
                fail(f"invalid testsuite attribute {key}={raw!r}")
                raise AssertionError("unreachable")
            totals[key] += value
    return totals


def enforce(
    counts: dict[str, int],
    *,
    max_skipped: int,
    max_failures: int,
    max_errors: int,
    min_tests: int,
) -> None:
    if counts["tests"] < min_tests:
        fail(f"insufficient tests: {counts['tests']} < min_tests {min_tests}")
    if counts["skipped"] > max_skipped:
        fail(f"skipped too high: {counts['skipped']} > max_skipped {max_skipped}")
    if counts["failures"] > max_failures:
        fail(
            f"failures too high: {counts['failures']} > max_failures {max_failures}"
        )
    if counts["errors"] > max_errors:
        fail(f"errors too high: {counts['errors']} > max_errors {max_errors}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--junit", type=Path, required=True)
    p.add_argument("--max-skipped", type=int, default=0)
    p.add_argument("--max-failures", type=int, default=0)
    p.add_argument("--max-errors", type=int, default=0)
    p.add_argument("--min-tests", type=int, default=1)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    counts = parse_junit(args.junit)
    enforce(
        counts,
        max_skipped=args.max_skipped,
        max_failures=args.max_failures,
        max_errors=args.max_errors,
        min_tests=args.min_tests,
    )
    print(
        "[JUNIT-SUMMARY] OK:",
        f"tests={counts['tests']}",
        f"failures={counts['failures']}",
        f"errors={counts['errors']}",
        f"skipped={counts['skipped']}",
    )


if __name__ == "__main__":
    main()
