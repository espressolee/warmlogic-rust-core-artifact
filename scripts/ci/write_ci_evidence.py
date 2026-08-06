#!/usr/bin/env python3
"""Write machine-readable CI gate evidence JSON."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--gate", required=True)
    p.add_argument("--workflow", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--run-attempt", required=True)
    p.add_argument("--event-name", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--job-status", required=True)
    p.add_argument(
        "--job-result",
        action="append",
        default=[],
        help="Per-job result in key=value format; may be passed multiple times.",
    )
    return p.parse_args()


def parse_job_results(items: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"invalid --job-result value: {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"invalid --job-result key in: {item!r}")
        results[key] = value
    return results


def main() -> None:
    args = parse_args()
    job_results = parse_job_results(args.job_result)
    payload = {
        "schema": "warmlogic.ci.evidence.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": args.gate,
        "workflow": args.workflow,
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "event_name": args.event_name,
        "ref": args.ref,
        "sha": args.sha,
        "job_status": args.job_status,
        "job_results": job_results,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[CI-EVIDENCE] wrote {args.out}")


if __name__ == "__main__":
    main()
