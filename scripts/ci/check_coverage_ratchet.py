#!/usr/bin/env python3
"""Fail CI when total coverage drops below ratchet baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COVERAGE = ROOT / "coverage.json"
DEFAULT_CONFIG = ROOT / "config" / "security" / "coverage_ratchet.json"


def fail(msg: str) -> None:
    print(f"[COVERAGE-RATCHET] ERROR: {msg}")
    sys.exit(1)


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def get_percent_covered(coverage_report: dict) -> float:
    totals = coverage_report.get("totals")
    if not isinstance(totals, dict):
        fail("coverage report missing 'totals' object")

    value = totals.get("percent_covered")
    if value is None:
        fail("coverage report missing totals.percent_covered")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        fail(f"invalid totals.percent_covered value: {value!r} ({exc})")
        raise  # unreachable, for type checkers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    coverage_report = load_json(args.coverage)
    cfg = load_json(args.config)

    baseline = cfg.get("minimum_total_percent")
    if baseline is None:
        fail(f"{args.config} missing minimum_total_percent")
    try:
        baseline = float(baseline)
    except (TypeError, ValueError) as exc:
        fail(f"invalid minimum_total_percent value: {baseline!r} ({exc})")

    observed = get_percent_covered(coverage_report)
    print(
        f"[COVERAGE-RATCHET] observed={observed:.4f}% "
        f"baseline={baseline:.4f}%"
    )

    if observed < baseline:
        fail(f"coverage dropped below ratchet baseline: {observed:.4f}% < {baseline:.4f}%")

    print("[COVERAGE-RATCHET] OK: coverage meets ratchet baseline")


if __name__ == "__main__":
    main()
