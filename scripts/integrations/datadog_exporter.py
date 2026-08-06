#!/usr/bin/env python3
import json
import time
from pathlib import Path


def export_to_datadog_format():
    print("Initializing WarmLogic Datadog Exporter...")

    # Simulate scanning out/audit for the latest metrics
    audit_dir = Path("out/audit")
    metrics = []

    for f in audit_dir.glob("*.json"):
        if f.name == "GRAND_UNIFIED_AUDIT_REPORT.md":
            continue
        with open(f, "r") as file:
            data = json.load(file)
            # Flatten some metrics for DD
            metric_base = f"warmlogic.audit.{f.stem}"
            metrics.append(
                {
                    "metric": f"{metric_base}.verdict",
                    "points": [
                        [int(time.time()), 1 if data.get("verdict") == "PASS" else 0]
                    ],
                    "type": "gauge",
                    "tags": ["version:3.2", "env:production"],
                }
            )

    # Mock output to a JSON file (enterprise ingest simulation)
    out_path = Path("out/integrations/datadog_metrics.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Successfully exported {len(metrics)} metrics to {out_path}")


if __name__ == "__main__":
    export_to_datadog_format()
