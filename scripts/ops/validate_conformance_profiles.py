#!/usr/bin/env python3
"""Validate conformance profile JSON against a JSON schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

PROFILE_KEY = {
    "witness": "witness_path",
    "p300": "window",
    "p400": "bounds",
}


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=sorted(PROFILE_KEY))
    parser.add_argument("payload")
    parser.add_argument("--schema", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload_path = Path(args.payload)
    schema_path = Path(args.schema)

    if not payload_path.is_file():
        print(f"ERROR: payload not found: {payload_path}")
        return 1
    if not schema_path.is_file():
        print(f"ERROR: schema not found: {schema_path}")
        return 1

    try:
        payload = _load_json(payload_path)
        schema = _load_json(schema_path)
        jsonschema.validate(payload, schema)
    except Exception as exc:
        print(f"ERROR: validation failed ({args.profile}): {exc}")
        return 1

    expected_key = PROFILE_KEY[args.profile]
    if expected_key not in payload:
        print(f"ERROR: '{expected_key}' key missing for profile '{args.profile}'")
        return 1

    print(
        f"conformance profile valid: profile={args.profile}, payload={payload_path}, schema={schema_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
