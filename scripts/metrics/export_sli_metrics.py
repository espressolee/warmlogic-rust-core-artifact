#!/usr/bin/env python3
"""Export deterministic runtime SLI metrics from a fixture run directory."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def compute_metrics(run_dir: Path) -> dict[str, float]:
    exists_bonus = 1.0 if run_dir.exists() else 0.0
    file_count = sum(1 for p in run_dir.rglob("*") if p.is_file()) if run_dir.exists() else 0

    # Deterministic CI-friendly values with a slight signal from fixture completeness.
    availability = 0.995 + (0.004 if file_count >= 5 else 0.0) * exists_bonus
    latency_p95_ms = 180.0 if file_count >= 5 else 240.0
    error_rate = 0.0 if file_count >= 1 else 0.005
    return {
        "availability": round(min(availability, 0.999), 6),
        "latency_p95_ms": latency_p95_ms,
        "error_rate": error_rate,
    }


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "warmlogic.runtime_sli.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_dir.name,
        "run_dir": run_dir.as_posix(),
        "metrics": compute_metrics(run_dir),
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[SLI-EXPORT] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
