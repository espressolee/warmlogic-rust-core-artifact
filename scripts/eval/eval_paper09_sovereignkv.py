#!/usr/bin/env python3
"""
Paper 09 workload micro-case: SovereignKV (DashMap in-memory store)

Goal:
- Connect the paper's "conversion semantics" result to a stateful, end-to-end-ish operation.
- Measure how a bytes payload is ingested into a Rust store when the API uses:
  1) bytes-like boundary (`set_bytes`: PyBytes -> explicit contiguous copy in Rust),
  2) binding-local extractor (`set_bytesvec`: BytesVec -> contiguous copy via bytes/buffer APIs),
  3) Vec<u8> boundary conversion (`set_vec`: Vec<u8> arg conversion; stock PyO3 uses sequence semantics for bytes).

This benchmark is intentionally simple:
- We measure per-op SET and GET latency for a fixed payload size across repeated runs.
- Results are reported as per-op latency (ns/op), with per-repeat p50/p99 and
  median/IQR across repeats.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import sys
import time
from typing import Any, Callable

# Import strategy (match eval_bridge_v3.py / eval_e2e_bytes_pipeline.py):
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


def _median_iqr(values: list[float]) -> dict[str, float]:
    values_sorted = sorted(values)
    if not values_sorted:
        return {"median": float("nan"), "iqr": float("nan")}
    q1 = values_sorted[int(len(values_sorted) * 0.25)]
    q3 = values_sorted[int(len(values_sorted) * 0.75)]
    return {"median": statistics.median(values_sorted), "iqr": q3 - q1}


def _p99(values: list[float]) -> float:
    if not values:
        return float("nan")
    values_sorted = sorted(values)
    idx = int(0.99 * (len(values_sorted) - 1))
    return values_sorted[idx]


def _bench_op_latencies_ns(
    fn: Callable[[], Any], *, warmup_ops: int, ops: int
) -> list[float]:
    for _ in range(warmup_ops):
        fn()

    latencies: list[float] = []
    for _ in range(ops):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        latencies.append(float(t1 - t0))
    return latencies


def _run_set_repeat(
    *,
    api: str,
    payload: bytes,
    keys: int,
    warmup_ops: int,
    ops: int,
) -> dict[str, float]:
    kv = warm_logic_rs.SovereignKV()
    key_list = [f"k{i}" for i in range(keys)]

    # Pre-size the map to a stable key set without paying the full payload cost.
    for k in key_list:
        kv.set_bytes(k, b"x")

    if api == "set_bytes":
        set_fn: Callable[[str, Any], Any] = kv.set_bytes
    elif api == "set_bytesvec":
        set_fn = kv.set_bytesvec
    elif api == "set_vec":
        set_fn = kv.set_vec
    else:
        raise ValueError(f"unknown api: {api}")

    i = 0
    def _one_op() -> None:
        nonlocal i
        set_fn(key_list[i % keys], payload)
        i += 1

    lat = _bench_op_latencies_ns(
        _one_op, warmup_ops=warmup_ops, ops=ops
    )
    return {"p50_ns": statistics.median(lat), "p99_ns": _p99(lat)}


def _run_get_repeat(
    *, payload: bytes, keys: int, warmup_ops: int, ops: int
) -> dict[str, float]:
    kv = warm_logic_rs.SovereignKV()
    key_list = [f"k{i}" for i in range(keys)]
    for k in key_list:
        kv.set_bytes(k, payload)

    i = 0
    def _one_op() -> None:
        nonlocal i
        v = kv.get_bytes(key_list[i % keys])
        if v is None or len(v) != len(payload):
            raise RuntimeError("content mismatch")
        i += 1

    lat = _bench_op_latencies_ns(
        _one_op, warmup_ops=warmup_ops, ops=ops
    )
    return {"p50_ns": statistics.median(lat), "p99_ns": _p99(lat)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper 09: SovereignKV workload")
    parser.add_argument("--run-id", default="paper09_sovkv")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup-ops", type=int, default=100, help="warmup ops per repeat")
    parser.add_argument("--ops", type=int, default=1000, help="timed ops per repeat")
    parser.add_argument("--keys", type=int, default=64, help="distinct keys (map stays bounded)")
    parser.add_argument("--size", type=int, default=1_000_000, help="payload bytes")
    args = parser.parse_args()

    payload = bytes([0xAB]) * args.size

    set_apis = ["set_bytes", "set_bytesvec", "set_vec"]
    results: list[dict[str, Any]] = []

    # SET variants.
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for api in set_apis:
            p50_samples: list[float] = []
            p99_samples: list[float] = []
            for _ in range(args.repeats):
                r = _run_set_repeat(
                    api=api,
                    payload=payload,
                    keys=args.keys,
                    warmup_ops=args.warmup_ops,
                    ops=args.ops,
                )
                p50_samples.append(r["p50_ns"])
                p99_samples.append(r["p99_ns"])
            results.append(
                {
                    "op": "set",
                    "api": api,
                    "repeats": args.repeats,
                    "p50_ns": _median_iqr(p50_samples),
                    "p99_ns": _median_iqr(p99_samples),
                }
            )

        # GET (single API: get_bytes).
        p50_samples = []
        p99_samples = []
        for _ in range(args.repeats):
            r = _run_get_repeat(
                payload=payload,
                keys=args.keys,
                warmup_ops=args.warmup_ops,
                ops=args.ops,
            )
            p50_samples.append(r["p50_ns"])
            p99_samples.append(r["p99_ns"])
        results.append(
            {
                "op": "get",
                "api": "get_bytes",
                "repeats": args.repeats,
                "p50_ns": _median_iqr(p50_samples),
                "p99_ns": _median_iqr(p99_samples),
            }
        )
    finally:
        if gc_was_enabled:
            gc.enable()

    out_dir = f"out/bridge_eval/{args.run_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "sovkv_telemetry.json")

    payload_json = {
        "metadata": {
            "run_id": args.run_id,
            "timestamp": time.time(),
            "repeats": args.repeats,
            "warmup_ops": args.warmup_ops,
            "ops": args.ops,
            "keys": args.keys,
            "payload_size_bytes": args.size,
            "gc_disabled": True,
            "platform": sys.platform,
            "python": sys.version,
            "import": {
                "use_installed": use_installed,
                "python_path": ext_path if not use_installed else None,
                "module_file": getattr(warm_logic_rs, "__file__", None),
            },
        },
        "results": results,
    }

    with open(out_path, "w") as f:
        json.dump(payload_json, f, indent=2)

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
