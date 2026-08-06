#!/usr/bin/env python3
"""
Paper 09: quantify the cost of safe GIL release patterns.

We measure a bandwidth-bound consumer (sum) for:
- immutable bytes: hold GIL vs allow_threads (no copy required)
- mutable buffer exporter (bytearray): hold GIL vs allow_threads (safe pattern = copy then allow_threads)

Outputs an aggregate JSON in the same style as eval_bridge_v3 telemetry (p50/p99 + IQR across repeats).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_warm_logic_rs() -> Any:
    # Match eval_bridge_v3.py import strategy.
    use_installed = os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1"
    ext_path = os.environ.get("WARM_LOGIC_RS_PYTHON_PATH")

    repo_root = str(_repo_root())
    if not use_installed:
        ext_path = ext_path or os.path.join(repo_root, "warm_logic_rs", "python_packages_v2")
        sys.path.insert(0, ext_path)
        sys.path.insert(1, repo_root)
    else:
        sys.path.append(repo_root)

    import warm_logic_rs  # type: ignore

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
    return warm_logic_rs


def _quantile(samples_sorted: list[float], q: float) -> float:
    if not samples_sorted:
        return float("nan")
    idx = int(len(samples_sorted) * q)
    idx = max(0, min(idx, len(samples_sorted) - 1))
    return samples_sorted[idx]


def _iqr(values: list[float]) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    return _quantile(s, 0.75) - _quantile(s, 0.25)


def _median(values: list[float]) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    return _quantile(s, 0.50)


def _measure_empty_loop(batch: int) -> int:
    start = time.perf_counter_ns()
    for _ in range(batch):
        pass
    end = time.perf_counter_ns()
    return end - start


def measure_corrected_ns_per_call(
    func: Callable[[Any], Any],
    arg: Any,
    *,
    iterations: int,
    batch: int,
    warmup: int,
) -> dict[str, float | int]:
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
    p50 = _quantile(corrected, 0.50)
    p99 = _quantile(corrected, 0.99)
    avg = statistics.mean(corrected)
    std = statistics.pstdev(corrected)

    return {
        "iterations": iterations,
        "batch": batch,
        "p50": p50,
        "p99": p99,
        "avg": avg,
        "std": std,
        "negatives_clamped": negative,
    }


def _try_git_rev() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="gil_tradeoff_macos_arm64")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--size", type=int, default=10_000_000)
    parser.add_argument("--out", default="out/bridge_eval/gil_tradeoff/gil_tradeoff.json")
    args = parser.parse_args()

    warm_logic_rs = _load_warm_logic_rs()

    size = int(args.size)
    bytes_data = b"\x00" * size
    bytearray_data = bytearray(bytes_data)
    mv_bytearray = memoryview(bytearray_data)

    paths: list[tuple[str, Callable[[Any], Any], Any]] = [
        ("Sum (PyBytes, hold GIL)", warm_logic_rs.benchmark_consume_step_5_sum, bytes_data),
        (
            "Sum (PyBytes, allow_threads)",
            warm_logic_rs.benchmark_consume_step_5_sum_allow_threads,
            bytes_data,
        ),
        (
            "Sum (bytearray buffer, hold GIL)",
            warm_logic_rs.benchmark_consume_buffer,
            mv_bytearray,
        ),
        (
            "Sum (bytearray buffer, allow_threads; copy+sum)",
            warm_logic_rs.benchmark_consume_buffer_allow_threads_copy_sum,
            mv_bytearray,
        ),
    ]

    runs: list[list[dict[str, Any]]] = []
    for _ in range(int(args.repeats)):
        rows: list[dict[str, Any]] = []
        for path, func, arg in paths:
            stats = measure_corrected_ns_per_call(
                func,
                arg,
                iterations=int(args.iterations),
                batch=int(args.batch),
                warmup=int(args.warmup),
            )
            rows.append(
                {
                    "path": path,
                    "size_bytes": size,
                    **stats,
                }
            )
        runs.append(rows)

    by_path: dict[str, dict[str, list[float]]] = {}
    for repeat in runs:
        for row in repeat:
            p = str(row["path"])
            slot = by_path.setdefault(p, {"p50": [], "p99": []})
            slot["p50"].append(float(row["p50"]))
            slot["p99"].append(float(row["p99"]))

    aggregate: list[dict[str, Any]] = []
    for path in [p for (p, _f, _a) in paths]:
        stats = by_path[path]
        aggregate.append(
            {
                "path": path,
                "size_bytes": size,
                "p50_median": _median(stats["p50"]),
                "p50_iqr": _iqr(stats["p50"]),
                "p99_median": _median(stats["p99"]),
                "p99_iqr": _iqr(stats["p99"]),
                "repeats": int(args.repeats),
            }
        )

    out = {
        "metadata": {
            "git": _try_git_rev(),
            "python": sys.version.splitlines()[0],
            "platform": platform.platform(),
            "cpu": platform.machine(),
        },
        "args": {
            "run_id": args.run_id,
            "repeats": int(args.repeats),
            "warmup": int(args.warmup),
            "iterations": int(args.iterations),
            "batch": int(args.batch),
            "size": size,
        },
        "runs": runs,
        "aggregate": aggregate,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

