#!/usr/bin/env python3
"""
Paper 09 ablation: `Vec<u8>` argument extraction across Python input types.

Motivation:
- PyO3's stock `Vec<T>` extraction uses generic sequence iteration.
- For byte payloads, many Python objects are both sequence-like and buffer-like.
- We measure how the `Vec<u8>` argument behaves for common byte-container inputs.

This script measures only one path:
  warm_logic_rs.benchmark_copy_vec_arg(x)  # where x converts to Vec<u8>

It uses the same empty-loop subtraction strategy as eval_bridge_v3.py to report
corrected per-call latencies, and aggregates medians across repeats.
"""

from __future__ import annotations

import argparse
import array as _array
import gc
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable


# Import strategy (match eval_bridge_v3.py):
use_installed = os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1"
ext_path = os.environ.get("WARM_LOGIC_RS_PYTHON_PATH")
repo_root = os.getcwd()
if not use_installed:
    ext_path = ext_path or os.path.join(repo_root, "warm_logic_rs", "python_packages_v2")
    sys.path.insert(0, ext_path)
    sys.path.insert(1, repo_root)
else:
    sys.path.append(repo_root)

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError as e:
    print(f"ERROR: Cannot import warm_logic_rs: {e}")
    sys.exit(1)


def _quantile(samples_sorted: list[float], q: float) -> float:
    if not samples_sorted:
        return float("nan")
    idx = int(len(samples_sorted) * q)
    idx = max(0, min(idx, len(samples_sorted) - 1))
    return samples_sorted[idx]


def _measure_empty_loop(batch: int) -> int:
    start = time.perf_counter_ns()
    for _ in range(batch):
        pass
    end = time.perf_counter_ns()
    return end - start


def _measure_corrected_ns_per_call(
    func: Callable[[Any], Any],
    arg: Any,
    *,
    iterations: int,
    batch: int,
    warmup: int,
) -> dict[str, float]:
    for _ in range(warmup):
        func(arg)

    corrected: list[float] = []
    negative = 0
    for _ in range(iterations):
        empty = _measure_empty_loop(batch)

        start = time.perf_counter_ns()
        for _ in range(batch):
            func(arg)
        end = time.perf_counter_ns()

        per_call = (end - start - empty) / batch
        if per_call < 0:
            negative += 1
            per_call = 0.0
        corrected.append(per_call)

    corrected.sort()
    return {
        "p50": _quantile(corrected, 0.50),
        "p99": _quantile(corrected, 0.99),
        "avg": statistics.mean(corrected),
        "std": statistics.pstdev(corrected),
        "negatives_clamped": float(negative),
    }


def _median_iqr(values: list[float]) -> dict[str, float]:
    xs = sorted(values)
    if not xs:
        return {"median": float("nan"), "iqr": float("nan")}
    q1 = xs[int(len(xs) * 0.25)]
    q3 = xs[int(len(xs) * 0.75)]
    return {"median": statistics.median(xs), "iqr": q3 - q1}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="vec_u8_input_variants")
    parser.add_argument("--size", type=int, default=10_000_000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--batch", type=int, default=1)
    args = parser.parse_args()

    b = b"\x00" * args.size

    variants: list[tuple[str, Any]] = [
        ("bytes", b),
        ("bytearray", bytearray(b)),
        ("memoryview(bytes)", memoryview(b)),
        ("memoryview(bytearray)", memoryview(bytearray(b))),
        ("array('B')", _array.array("B", b)),
    ]

    func = warm_logic_rs.benchmark_copy_vec_arg

    meta = {
        "run_id": args.run_id,
        "timestamp": time.time(),
        "platform": platform.platform(),
        "python": sys.version,
        "params": {
            "size_bytes": args.size,
            "repeats": args.repeats,
            "warmup": args.warmup,
            "iterations": args.iterations,
            "batch": args.batch,
        },
        "import": {
            "use_installed": use_installed,
            "python_path": ext_path,
            "module_file": getattr(warm_logic_rs, "__file__", None),
        },
    }

    runs: list[dict[str, Any]] = []
    aggregate_p50: dict[str, list[float]] = {name: [] for name, _ in variants}
    aggregate_p99: dict[str, list[float]] = {name: [] for name, _ in variants}

    gc.disable()
    try:
        for r in range(args.repeats):
            per_repeat: list[dict[str, Any]] = []
            for name, obj in variants:
                s = _measure_corrected_ns_per_call(
                    func,
                    obj,
                    iterations=args.iterations,
                    batch=args.batch,
                    warmup=args.warmup,
                )
                per_repeat.append({"input": name, "size_bytes": args.size, **s})
                aggregate_p50[name].append(float(s["p50"]))
                aggregate_p99[name].append(float(s["p99"]))
                print(f"[{r+1}/{args.repeats}] {name:<20} p50={s['p50']:.0f}ns p99={s['p99']:.0f}ns")
            runs.append({"repeat": r, "results": per_repeat})
    finally:
        gc.enable()

    aggregate: list[dict[str, Any]] = []
    for name, _obj in variants:
        p50 = _median_iqr(aggregate_p50[name])
        p99 = _median_iqr(aggregate_p99[name])
        aggregate.append(
            {
                "input": name,
                "size_bytes": args.size,
                "repeats": args.repeats,
                "p50_median": p50["median"],
                "p50_iqr": p50["iqr"],
                "p99_median": p99["median"],
                "p99_iqr": p99["iqr"],
            }
        )

    out_dir = Path("out/bridge_eval") / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "vec_u8_input_variants.json"
    out_path.write_text(json.dumps({"metadata": meta, "runs": runs, "aggregate": aggregate}, indent=2), encoding="utf-8")
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()

