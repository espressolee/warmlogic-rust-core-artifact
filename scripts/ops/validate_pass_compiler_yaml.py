#!/usr/bin/env python3
"""Validate CE PASS compiler example (JSON/YAML-subset)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_KEYS = {"ce_id", "expected", "input"}
ALLOWED_EXPECTED = {"compile_fail", "compile_pass"}


def _err(message: str) -> int:
    print(f"ERROR: {message}")
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_pass_compiler_yaml.py <ce-example.yaml>")
        return 2

    path = Path(sys.argv[1])
    if not path.is_file():
        return _err(f"input not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _err(f"expected JSON-compatible YAML content: {exc}")

    if not isinstance(payload, dict):
        return _err("top-level payload must be an object")

    missing = sorted(REQUIRED_KEYS - payload.keys())
    if missing:
        return _err(f"missing required key(s): {', '.join(missing)}")

    expected = str(payload.get("expected", ""))
    if expected not in ALLOWED_EXPECTED:
        return _err(
            f"invalid expected='{expected}', allowed={sorted(ALLOWED_EXPECTED)}"
        )

    ce_id = str(payload.get("ce_id", ""))
    if not ce_id.startswith("CE-"):
        return _err("ce_id must start with 'CE-'")

    print(f"PASS compiler example valid: ce_id={ce_id}, expected={expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
