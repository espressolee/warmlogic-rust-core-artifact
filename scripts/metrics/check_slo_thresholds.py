#!/usr/bin/env python3
"""Check SLI payload against SLO thresholds and optionally emit alert evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sli-path", required=True)
    parser.add_argument("--thresholds", required=True)
    parser.add_argument("--alert-webhook")
    parser.add_argument("--ce-ledger")
    return parser.parse_args()


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"missing file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def append_ce_ledger(ledger_path: str | None, event: dict) -> None:
    if not ledger_path:
        return
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    sli = load_json(args.sli_path)
    policy = load_json(args.thresholds)

    metrics = sli.get("metrics", {})
    thresholds = policy.get("thresholds", {})

    availability = float(metrics.get("availability", 0.0))
    latency = float(metrics.get("latency_p95_ms", 10**9))
    error_rate = float(metrics.get("error_rate", 1.0))

    availability_min = float(thresholds.get("availability_min", 0.0))
    latency_max = float(thresholds.get("latency_p95_ms_max", 10**9))
    error_rate_max = float(thresholds.get("error_rate_max", 1.0))

    breaches = []
    if availability < availability_min:
        breaches.append("availability")
    if latency > latency_max:
        breaches.append("latency_p95_ms")
    if error_rate > error_rate_max:
        breaches.append("error_rate")

    event = {
        "schema": "warmlogic.slo_check_event.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": sli.get("run_id"),
        "breaches": breaches,
        "alert_webhook_configured": bool(args.alert_webhook),
    }
    append_ce_ledger(args.ce_ledger, event)

    if breaches:
        print(f"[SLO-CHECK] FAIL: breaches={','.join(breaches)}")
        return 1

    print("[SLO-CHECK] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
