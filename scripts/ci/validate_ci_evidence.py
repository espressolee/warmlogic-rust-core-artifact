#!/usr/bin/env python3
"""Validate CI evidence JSON against local contract."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config" / "security" / "ci_evidence_contract.json"


def fail(msg: str) -> None:
    print(f"[CI-EVIDENCE-VALIDATE] ERROR: {msg}")
    sys.exit(1)


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing file: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        fail(f"invalid json in {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"expected top-level object in {path}")
    return data


def ensure_non_empty_string(payload: dict, field: str) -> None:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        fail(f"field '{field}' must be a non-empty string")


def parse_timestamp(value: str) -> None:
    candidate = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as exc:
        fail(f"generated_at_utc must be ISO-8601 timestamp: {exc}")
    if dt.tzinfo is None:
        fail("generated_at_utc must include timezone")


def validate(payload: dict, contract: dict) -> None:
    required_fields = contract.get("required_top_level_fields", [])
    if not isinstance(required_fields, list) or not required_fields:
        fail("contract required_top_level_fields must be a non-empty list")
    for field in required_fields:
        if field not in payload:
            fail(f"missing required field: {field}")

    expected_schema = contract.get("expected_schema")
    if payload.get("schema") != expected_schema:
        fail(
            f"unexpected schema value: {payload.get('schema')!r} "
            f"(expected {expected_schema!r})"
        )

    required_str = contract.get("required_non_empty_string_fields", [])
    if not isinstance(required_str, list):
        fail("contract required_non_empty_string_fields must be a list")
    for field in required_str:
        ensure_non_empty_string(payload, field)

    parse_timestamp(str(payload["generated_at_utc"]))

    allowed_status = contract.get("allowed_job_status", [])
    if not isinstance(allowed_status, list) or not allowed_status:
        fail("contract allowed_job_status must be a non-empty list")
    status = payload.get("job_status")
    if status not in set(allowed_status):
        fail(f"job_status must be one of {allowed_status}, got {status!r}")

    job_results = payload.get("job_results")
    if not isinstance(job_results, dict):
        fail("job_results must be an object")

    min_job_results = contract.get("min_job_results", 1)
    try:
        min_job_results = int(min_job_results)
    except (TypeError, ValueError):
        fail(f"contract min_job_results must be an integer, got {min_job_results!r}")
    if min_job_results < 1:
        fail("contract min_job_results must be >= 1")
    if len(job_results) < min_job_results:
        fail(
            f"job_results must contain at least {min_job_results} entries "
            f"(got {len(job_results)})"
        )

    for key, value in job_results.items():
        if not isinstance(key, str) or not key.strip():
            fail("job_results contains empty/non-string key")
        if not isinstance(value, str) or not value.strip():
            fail(f"job_results[{key!r}] must be a non-empty string")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = load_json(args.input)
    contract = load_json(args.contract)
    validate(payload, contract)
    print(
        "[CI-EVIDENCE-VALIDATE] OK:",
        f"gate={payload.get('gate')}",
        f"status={payload.get('job_status')}",
    )


if __name__ == "__main__":
    main()
