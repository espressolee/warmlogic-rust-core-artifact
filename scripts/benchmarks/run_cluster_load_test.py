# ==========================================================
# Module: run_cluster_load_test.py
# Project: Warm Logic — Model Layer
# Description: Perf/load-test harness aligned with Protocol_Bound_Perf_Spec_P300_v1.
# Author: espressolee (updated by automation)
# ==========================================================

"""Perf/load-test harness aligned with Protocol_Bound_Perf_Spec_P300_v1."""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class PerfRecord:
    workload_id: str
    sessions: int
    duration_sec: int
    elapsed_sec: float
    iterations: int
    throughput: float
    autonomy_mode: str
    slo: Dict[str, float] = field(default_factory=dict)
    notes: str = ""
    schema_version: str = "perf_load_test_v1"


def simulate_sessions(concurrency: int, duration: int) -> Dict[str, float]:
    """Simulate load and return simple statistics."""
    start = time.time()
    iterations = 0
    sleep_interval = max(0.02, 0.2 / max(1, concurrency))
    while time.time() - start < duration:
        iterations += max(concurrency, 1)
        time.sleep(sleep_interval)
        _ = random.random()
    elapsed = time.time() - start
    throughput = iterations / elapsed if elapsed else 0.0
    return {"elapsed": elapsed, "iterations": iterations, "throughput": throughput}


def build_perf_record(
    stats: Dict[str, float],
    *,
    workload_id: str,
    sessions: int,
    duration: int,
    autonomy_mode: str,
    throughput_slo: float | None,
    queue95_slo: float | None,
    notes: str,
) -> PerfRecord:
    slo: Dict[str, float] = {}
    if throughput_slo is not None:
        slo["throughput_min"] = throughput_slo
    if queue95_slo is not None:
        slo["queue95_ms"] = queue95_slo
    return PerfRecord(
        workload_id=workload_id,
        sessions=sessions,
        duration_sec=duration,
        elapsed_sec=stats.get("elapsed", 0.0),
        iterations=int(stats.get("iterations", 0.0)),
        throughput=stats.get("throughput", 0.0),
        autonomy_mode=autonomy_mode,
        slo=slo,
        notes=notes,
    )


def _write_report(path: Path, row: Dict[str, float], *, header: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _write_perf_json(path: Path, record: PerfRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate cluster load (perf harness)")
    parser.add_argument("--sessions", type=int, default=5, help="Concurrent shell sessions")
    parser.add_argument("--duration", type=int, default=2, help="Duration in seconds")
    parser.add_argument("--label", default="default", help="Label / notes for reports")
    parser.add_argument("--dry-run", action="store_true", help="Print parameters and exit")
    parser.add_argument("--workload-id", default="PERF-CLUSTER-S", help="Workload ID from CT_Safe_Load_Test_Spec")
    parser.add_argument("--autonomy-mode", default="A0", help="Autonomy mode during the run")
    parser.add_argument("--throughput-slo", type=float, default=25.0, help="Expected throughput target")
    parser.add_argument("--queue95-slo", type=float, default=500.0, help="Expected queue95 target (ms)")
    parser.add_argument(
        "--report-csv",
        type=Path,
        default=Path("docs/research/eval/e2_loadtest_summary.csv"),
        help="Optional CSV file to append run stats",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("out/perf/load_tests/load_test.json"),
        help="Write perf_load_test_v1 JSON",
    )
    args = parser.parse_args(argv)

    print(
        f"[cluster-load] workload={args.workload_id} label={args.label} sessions={args.sessions} "
        f"duration={args.duration}s dry_run={args.dry_run}"
    )
    stats = {"elapsed": 0.0, "iterations": 0.0, "throughput": 0.0}
    if not args.dry_run:
        stats = simulate_sessions(args.sessions, args.duration)
    print(
        "[cluster-load] complete elapsed={elapsed:.2f}s iterations={iterations} "
        "throughput={throughput:.2f}".format(**stats)
    )

    if not args.dry_run and args.out_json:
        record = build_perf_record(
            stats,
            workload_id=args.workload_id,
            sessions=args.sessions,
            duration=args.duration,
            autonomy_mode=args.autonomy_mode,
            throughput_slo=args.throughput_slo,
            queue95_slo=args.queue95_slo,
            notes=args.label,
        )
        _write_perf_json(args.out_json, record)
        print(f"[cluster-load] wrote JSON metrics to {args.out_json}")

    if not args.dry_run and args.report_csv:
        row = {
            "label": args.label,
            "workload_id": args.workload_id,
            "sessions": args.sessions,
            "duration": args.duration,
            "elapsed": f"{stats['elapsed']:.2f}",
            "iterations": int(stats["iterations"]),
            "throughput": f"{stats['throughput']:.2f}",
        }
        _write_report(args.report_csv, row, header=list(row.keys()))
        print(f"[cluster-load] appended metrics to {args.report_csv}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
