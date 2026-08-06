#!/usr/bin/env python3
"""Validate generated governance artifacts for CI sanity."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "logs" / "governance" / "GOVDEC-WLPv4-CI.json"


def main() -> int:
    if not DEFAULT_PATH.exists():
        print(f"[GOV-VALIDATE] ERROR: missing artifact {DEFAULT_PATH}")
        return 1

    payload = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    required = ("schema", "decision_id", "mode", "env_scope", "autonomy_cap", "verdict")
    missing = [key for key in required if key not in payload]
    if missing:
        print(f"[GOV-VALIDATE] ERROR: missing keys {missing}")
        return 1
    if payload.get("verdict") not in {"allow", "deny", "review"}:
        print("[GOV-VALIDATE] ERROR: invalid verdict")
        return 1

    print("[GOV-VALIDATE] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

