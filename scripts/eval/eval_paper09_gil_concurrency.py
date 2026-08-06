#!/usr/bin/env python3
"""
Paper 09: concurrency-bearing benchmark for the "copy then allow_threads" pattern.

Goal (strong-accept direction):
- Demonstrate that the `Vec<u8>` conversion semantic mismatch is not just a per-call slowdown,
  but can destroy throughput under multi-threaded request-style call patterns when the Rust side
  releases the GIL (`allow_threads`) for O(N) work.

Measured patterns (all do an O(N) sum under allow_threads):
- Sum (PyBytes, allow_threads): no copy (immutable bytes are stable under GIL release)
- Sum (BytesVec, allow_threads): forces contiguous copy via binding-local extractor, then releases GIL
- Sum (Vec<u8> arg, allow_threads): uses PyO3 `Vec<u8>` argument conversion, then releases GIL
  - stock PyO3 v0.22: bytes->Vec<u8> follows sequence semantics (element-wise), holds GIL for ms
  - patched PyO3: contiguous-copy fast path, holds GIL for ~copy time

We run a fixed number of calls per thread and report throughput and tail latency (p99/p999) with
median/IQR across repeats.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
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


def _try_cmd(cmd: list[str]) -> str | None:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception:
        return None


def _quantile(xs_sorted: list[float], q: float) -> float:
    if not xs_sorted:
        return float("nan")
    idx = int(len(xs_sorted) * q)
    idx = max(0, min(idx, len(xs_sorted) - 1))
    return xs_sorted[idx]


def _median_iqr(values: list[float]) -> dict[str, float]:
    xs = sorted(values)
    if not xs:
        return {"median": float("nan"), "iqr": float("nan")}
    q1 = _quantile(xs, 0.25)
    q3 = _quantile(xs, 0.75)
    return {"median": statistics.median(xs), "iqr": q3 - q1}


def _p99(values: list[float]) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    return _quantile(xs, 0.99)


def _p999(values: list[float]) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    return _quantile(xs, 0.999)


def _run_threaded_calls(
    *,
    func: Callable[[Any], Any],
    arg: Any,
    threads: int,
    warmup_calls_per_thread: int,
    calls_per_thread: int,
) -> dict[str, Any]:
    if threads <= 0:
        raise ValueError("threads must be > 0")
    if calls_per_thread <= 0:
        raise ValueError("calls_per_thread must be > 0")

    barrier = threading.Barrier(threads + 1)
    per_call_ns: list[float] = []
    per_call_lock = threading.Lock()

    def worker() -> None:
        # Optional warmup per thread (kept small; stock Vec<u8> can be very slow).
        for _ in range(warmup_calls_per_thread):
            func(arg)

        barrier.wait()
        local: list[float] = []
        for _ in range(calls_per_thread):
            t0 = time.perf_counter_ns()
            func(arg)
            t1 = time.perf_counter_ns()
            local.append(float(t1 - t0))

        with per_call_lock:
            per_call_ns.extend(local)

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for th in workers:
        th.start()

    barrier.wait()
    t_start = time.perf_counter_ns()
    for th in workers:
        th.join()
    t_end = time.perf_counter_ns()

    duration_s = max(1e-9, (t_end - t_start) / 1e9)
    total_calls = threads * calls_per_thread
    throughput = total_calls / duration_s

    return {
        "threads": threads,
        "calls_per_thread": calls_per_thread,
        "total_calls": total_calls,
        "duration_s": duration_s,
        "throughput_calls_per_s": throughput,
        "call_p50_ns": statistics.median(per_call_ns) if per_call_ns else float("nan"),
        "call_p99_ns": _p99(per_call_ns),
        "call_p999_ns": _p999(per_call_ns),
        "call_samples": len(per_call_ns),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="gil_concurrency_macos_arm64")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--size", type=int, default=10_000_000)
    parser.add_argument("--threads", default="1,8", help="Comma-separated thread counts.")
    parser.add_argument("--warmup-calls-per-thread", type=int, default=1)
    parser.add_argument("--calls-per-thread", type=int, default=20)
    parser.add_argument(
        "--out",
        default="out/bridge_eval/gil_concurrency/gil_concurrency.json",
    )
    args = parser.parse_args()

    warm_logic_rs = _load_warm_logic_rs()

    size = int(args.size)
    payload = b"\xAB" * size

    patterns: list[tuple[str, Callable[[Any], Any], Any]] = [
        ("Sum (PyBytes, allow_threads)", warm_logic_rs.benchmark_consume_step_5_sum_allow_threads, payload),
        ("Sum (BytesVec, allow_threads)", warm_logic_rs.benchmark_consume_bytesvec_allow_threads_sum, payload),
        ("Sum (Vec<u8> arg, allow_threads)", warm_logic_rs.benchmark_consume_vec_allow_threads_sum, payload),
    ]

    threads_list = [int(x.strip()) for x in str(args.threads).split(",") if x.strip()]

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        runs: list[dict[str, Any]] = []
        for name, func, arg in patterns:
            for threads in threads_list:
                thr_samples: list[float] = []
                p50_samples: list[float] = []
                p99_samples: list[float] = []
                p999_samples: list[float] = []
                duration_samples: list[float] = []

                for _ in range(int(args.repeats)):
                    r = _run_threaded_calls(
                        func=func,
                        arg=arg,
                        threads=threads,
                        warmup_calls_per_thread=int(args.warmup_calls_per_thread),
                        calls_per_thread=int(args.calls_per_thread),
                    )
                    thr_samples.append(float(r["throughput_calls_per_s"]))
                    p50_samples.append(float(r["call_p50_ns"]))
                    p99_samples.append(float(r["call_p99_ns"]))
                    p999_samples.append(float(r["call_p999_ns"]))
                    duration_samples.append(float(r["duration_s"]))

                runs.append(
                    {
                        "pattern": name,
                        "size_bytes": size,
                        "threads": threads,
                        "repeats": int(args.repeats),
                        "calls_per_thread": int(args.calls_per_thread),
                        "warmup_calls_per_thread": int(args.warmup_calls_per_thread),
                        "duration_s": _median_iqr(duration_samples),
                        "throughput_calls_per_s": _median_iqr(thr_samples),
                        "call_p50_ns": _median_iqr(p50_samples),
                        "call_p99_ns": _median_iqr(p99_samples),
                        "call_p999_ns": _median_iqr(p999_samples),
                    }
                )
    finally:
        if gc_was_enabled:
            gc.enable()

    out = {
        "metadata": {
            "python": sys.version.splitlines()[0],
            "platform": platform.platform(),
            "cpu": platform.machine(),
            "import": {
                "use_installed": os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1",
                "module_file": getattr(warm_logic_rs, "__file__", None),
            },
            "tool_versions": {
                "rustc": _try_cmd(["rustc", "--version"]),
                "cargo": _try_cmd(["cargo", "--version"]),
                "maturin": _try_cmd([sys.executable, "-m", "maturin", "--version"]),
                "pip": _try_cmd([sys.executable, "-m", "pip", "--version"]),
            },
        },
        "args": {
            "run_id": str(args.run_id),
            "repeats": int(args.repeats),
            "size": size,
            "threads": threads_list,
            "warmup_calls_per_thread": int(args.warmup_calls_per_thread),
            "calls_per_thread": int(args.calls_per_thread),
        },
        "results": runs,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

