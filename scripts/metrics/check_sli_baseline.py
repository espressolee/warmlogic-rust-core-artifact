#!/usr/bin/env python3
"""Validate runtime SLI metrics against baseline bounds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--baseline", required=True)
    return parser.parse_args()


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"missing file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    metrics_payload = load_json(args.metrics)
    baseline_payload = load_json(args.baseline)

    metrics = metrics_payload.get("metrics", {})
    thresholds = baseline_payload.get("thresholds", {})

    availability = float(metrics.get("availability", 0.0))
    latency = float(metrics.get("latency_p95_ms", 10**9))
    error_rate = float(metrics.get("error_rate", 1.0))

    availability_min = float(thresholds.get("availability_min", 0.0))
    latency_max = float(thresholds.get("latency_p95_ms_max", 10**9))
    error_rate_max = float(thresholds.get("error_rate_max", 1.0))

    violations = []
    if availability < availability_min:
        violations.append(
            f"availability {availability:.6f} < baseline min {availability_min:.6f}"
        )
    if latency > latency_max:
        violations.append(f"latency_p95_ms {latency:.2f} > baseline max {latency_max:.2f}")
    if error_rate > error_rate_max:
        violations.append(f"error_rate {error_rate:.6f} > baseline max {error_rate_max:.6f}")

    if violations:
        print("[SLI-BASELINE] FAIL")
        for item in violations:
            print(f"  - {item}")
        return 1

    print("[SLI-BASELINE] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

