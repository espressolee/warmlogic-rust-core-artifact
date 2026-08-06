#!/usr/bin/env python3
"""
Sparse-call latency probe for Paper 09.

The main harness (eval_bridge_v3.py) measures in tight loops ("hot").
This script measures per-call latency when calls are *not* batched, with an optional
sleep between calls to approximate sparse scheduling.

Notes:
- This does NOT attempt to fully control CPU frequency, OS scheduling, or i-cache state.
- It is intended as a "threats-to-validity" / sanity check, not a definitive cold-start study.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

# Import strategy matches eval_bridge_v3.py:
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
    print(f"Failed to load warm_logic_rs: {e}")
    sys.exit(1)


def _quantile(values_sorted: list[float], q: float) -> float:
    if not values_sorted:
        return float("nan")
    idx = int(len(values_sorted) * q)
    idx = max(0, min(idx, len(values_sorted) - 1))
    return values_sorted[idx]


def _summarize_ns(samples: list[int]) -> dict[str, float]:
    xs = sorted(float(x) for x in samples)
    return {
        "n": float(len(xs)),
        "median_ns": statistics.median(xs) if xs else float("nan"),
        "p90_ns": _quantile(xs, 0.90),
        "p99_ns": _quantile(xs, 0.99),
        "iqr_ns": (_quantile(xs, 0.75) - _quantile(xs, 0.25)) if xs else float("nan"),
    }


def _measure_sparse(
    func: Callable[[Any], Any],
    arg: Any,
    *,
    samples: int,
    warmup: int,
    sleep_ms: float,
) -> list[int]:
    for _ in range(warmup):
        func(arg)

    out: list[int] = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        func(arg)
        end = time.perf_counter_ns()
        out.append(end - start)
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="sparse_calls")
    parser.add_argument("--sizes", default="1000,10000000")
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--sleep-ms", type=float, default=1.0)
    args = parser.parse_args()

    sizes = [int(x.strip()) for x in args.sizes.split(",") if x.strip()]
    if not sizes:
        raise SystemExit("--sizes must contain at least one integer")

    gc.disable()
    try:
        meta = {
            "run_id": args.run_id,
            "timestamp": time.time(),
            "platform": platform.platform(),
            "python": sys.version,
            "params": {
                "sizes": sizes,
                "samples": args.samples,
                "warmup": args.warmup,
                "sleep_ms": args.sleep_ms,
            },
            "import": {
                "use_installed": use_installed,
                "python_path": ext_path,
                "module_file": getattr(warm_logic_rs, "__file__", None),
            },
        }

        results: list[dict[str, Any]] = []

        def py_noop(_: Any) -> int:
            return 0

        for size in sizes:
            b = b"\x00" * size
            mv = memoryview(b)

            paths: list[tuple[str, Callable[[Any], Any], Any]] = [
                ("Python noop", py_noop, b),
                ("C noop", lambda _x: warm_logic_rs.benchmark_c_noop(), None),
                ("Null (PyBytes)", warm_logic_rs.benchmark_zero_copy, b),
                ("Acquire buffer (len_bytes)", warm_logic_rs.benchmark_acquire_buffer_len, mv),
                ("Null (PyBuffer)", warm_logic_rs.benchmark_zero_copy_buffer, mv),
            ]

            for name, func, arg in paths:
                samples = _measure_sparse(
                    func,
                    arg,
                    samples=args.samples,
                    warmup=args.warmup,
                    sleep_ms=args.sleep_ms,
                )
                results.append(
                    {
                        "path": name,
                        "size_bytes": size,
                        "stats": _summarize_ns(samples),
                    }
                )

                s = results[-1]["stats"]
                print(
                    f"{name:<24} size={size:>9}  median={s['median_ns']:.1f}ns  p99={s['p99_ns']:.1f}ns  iqr={s['iqr_ns']:.1f}ns"
                )

        out_dir = Path("out/bridge_eval/sparse_calls")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{args.run_id}.json"
        out_path.write_text(json.dumps({"metadata": meta, "results": results}, indent=2), encoding="utf-8")
        print(f"\nWrote: {out_path}")
    finally:
        gc.enable()


if __name__ == "__main__":
    main()

