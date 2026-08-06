# ==========================================================
# Module: check_audit_retention.py
# Project: Warm Logic — Model Layer
# Description: Auto-inserted header (add description).
# Author: espressolee
# ==========================================================

#!/usr/bin/env python3
"""Check audit event retention age and emptiness."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_AUDIT_LOG = Path("out/audit_events.jsonl")


def _load_events(log_path: Path) -> List[Dict[str, Any]]:
    if not log_path.exists():
        raise FileNotFoundError(f"Audit log missing: {log_path}")
    events: List[Dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    if not events:
        raise RuntimeError("Audit log is empty")
    return events


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def check_retention(log_path: Path, max_age_days: float | None) -> None:
    events = _load_events(log_path)
    times = [
        ts
        for ts in (
            _parse_ts(evt.get("created_at") or evt.get("timestamp")) for evt in events
        )
        if ts
    ]
    if max_age_days is None or not times:
        return
    newest = max(times)
    age = (datetime.now(timezone.utc) - newest).total_seconds() / 86400.0
    if age > max_age_days:
        raise RuntimeError(
            f"Latest audit event is {age:.2f} days old (limit {max_age_days})"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check audit event retention")
    parser.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG)
    parser.add_argument("--max-age-days", type=float, default=90.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    check_retention(args.audit_log, args.max_age_days)
    print("[audit-retention] OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
