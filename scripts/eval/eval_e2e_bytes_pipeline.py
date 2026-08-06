#!/usr/bin/env python3
"""
E2E Benchmark (byte payloads): sign → verify → store

Goal:
- Provide an end-to-end workload which actually uses bytes-like payloads so the paper's
  byte-boundary results apply.
- Compare three conversion semantics:
  1) view: message is `bytes` borrowed as `&[u8]` in Rust (no input copy)
  2) vec: message is converted to `Vec<u8>` at the boundary (contiguous-copy on patched PyO3)
  3) sequence: message is iterated element-by-element in Rust (models stock PyO3 `Vec<T>` semantics)
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SizeParams:
    iterations: int
    messages: int


def _params_for_size(size: int) -> SizeParams:
    if size <= 100:
        return SizeParams(iterations=200, messages=10)
    if size <= 1_000:
        return SizeParams(iterations=100, messages=10)
    if size <= 10_000:
        return SizeParams(iterations=20, messages=5)
    return SizeParams(iterations=5, messages=3)


def _median_iqr(values: list[float]) -> dict[str, float]:
    values_sorted = sorted(values)
    if not values_sorted:
        return {"median": float("nan"), "iqr": float("nan")}
    q1 = values_sorted[int(len(values_sorted) * 0.25)]
    q3 = values_sorted[int(len(values_sorted) * 0.75)]
    return {"median": statistics.median(values_sorted), "iqr": q3 - q1}


def _make_messages(size: int, count: int) -> list[bytes]:
    msgs: list[bytes] = []
    for i in range(count):
        msgs.append(bytes([i & 0xFF]) * size)
    return msgs


def _bench_ns_per_op(
    func: Callable[[], Any], *, warmup: int, iterations: int
) -> float:
    gc.disable()
    try:
        for _ in range(warmup):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        end = time.perf_counter_ns()
        return (end - start) / iterations
    finally:
        gc.enable()


def _run_one_variant(
    *,
    variant: str,
    public_key: str,
    private_key: str,
    size: int,
    warmup: int,
    iterations: int,
    message_count: int,
) -> dict[str, float]:
    msgs = _make_messages(size, message_count)

    if variant == "view":
        sign = lambda m: warm_logic_rs.sign_bytes_view(private_key, m)
        verify = lambda m, s: warm_logic_rs.verify_bytes_view(public_key, m, s)
    elif variant == "vec":
        sign = lambda m: warm_logic_rs.sign_bytes_vec(private_key, m)
        verify = lambda m, s: warm_logic_rs.verify_bytes_vec(public_key, m, s)
    elif variant == "sequence":
        sign = lambda m: warm_logic_rs.sign_bytes_sequence(private_key, m)
        verify = lambda m, s: warm_logic_rs.verify_bytes_sequence(public_key, m, s)
    else:
        raise ValueError(f"unknown variant: {variant}")

    # Pre-sign once for verify-only.
    sigs = [sign(m) for m in msgs]

    # Store setup (fresh db per size/variant to reduce cross-test interference).
    tmp_dir = tempfile.mkdtemp(prefix=f"e2e_bytes_{variant}_")
    store = warm_logic_rs.SovereignStore(os.path.join(tmp_dir, "bench_db"))

    try:
        sign_only = _bench_ns_per_op(
            lambda: [sign(m) for m in msgs],
            warmup=warmup,
            iterations=iterations,
        ) / len(msgs)

        verify_only = _bench_ns_per_op(
            lambda: [verify(m, s) for m, s in zip(msgs, sigs)],
            warmup=warmup,
            iterations=iterations,
        ) / len(msgs)

        def _store_once() -> None:
            for i, (m, s) in enumerate(zip(msgs, sigs)):
                # Unique key per call to avoid overwriting.
                key = s + i.to_bytes(4, "little", signed=False)
                store.put_bytes(key, m)

        store_only = _bench_ns_per_op(
            _store_once,
            warmup=0,
            iterations=max(1, iterations // 2),
        ) / len(msgs)

        def _pipeline_once() -> None:
            for i, m in enumerate(msgs):
                s = sign(m)
                ok = verify(m, s)
                if ok:
                    key = s + i.to_bytes(4, "little", signed=False)
                    store.put_bytes(key, m)

        pipeline = _bench_ns_per_op(
            _pipeline_once,
            warmup=0,
            iterations=max(1, iterations // 2),
        ) / len(msgs)

        return {
            "sign_ns": sign_only,
            "verify_ns": verify_only,
            "store_ns": store_only,
            "pipeline_ns": pipeline,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E bytes pipeline benchmark")
    parser.add_argument("--run-id", default="e2e_bytes_pipeline")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=10)
    args = parser.parse_args()

    public_key, private_key = warm_logic_rs.generate_keypair()

    sizes = [100, 1_000, 10_000, 100_000]
    variants = ["view", "vec", "sequence"]

    all_rows: list[dict[str, Any]] = []

    for size in sizes:
        sp = _params_for_size(size)
        for variant in variants:
            sign_samples: list[float] = []
            verify_samples: list[float] = []
            store_samples: list[float] = []
            pipe_samples: list[float] = []

            for _ in range(args.repeats):
                r = _run_one_variant(
                    variant=variant,
                    public_key=public_key,
                    private_key=private_key,
                    size=size,
                    warmup=args.warmup,
                    iterations=sp.iterations,
                    message_count=sp.messages,
                )
                sign_samples.append(r["sign_ns"])
                verify_samples.append(r["verify_ns"])
                store_samples.append(r["store_ns"])
                pipe_samples.append(r["pipeline_ns"])

            all_rows.append(
                {
                    "variant": variant,
                    "message_size_bytes": size,
                    "repeats": args.repeats,
                    "params": {"iterations": sp.iterations, "messages": sp.messages},
                    "sign": _median_iqr(sign_samples),
                    "verify": _median_iqr(verify_samples),
                    "store": _median_iqr(store_samples),
                    "pipeline": _median_iqr(pipe_samples),
                }
            )

    out_dir = f"out/bridge_eval/{args.run_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "e2e_bytes_telemetry.json")
    payload = {
        "metadata": {
            "run_id": args.run_id,
            "timestamp": time.time(),
            "repeats": args.repeats,
            "warmup": args.warmup,
            "sizes": sizes,
            "variants": variants,
            "platform": sys.platform,
            "python": sys.version,
        },
        "results": all_rows,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote: {out_path}")

    print("\nSummary (p50 median, µs/op; IQR in µs)")
    for row in all_rows:
        def fmt(cell: dict[str, float]) -> str:
            return f"{cell['median']/1000:8.2f} ({cell['iqr']/1000:6.2f})"

        print(
            f"{row['variant']:>8} size={row['message_size_bytes']:>7}B | "
            f"sign {fmt(row['sign'])} | verify {fmt(row['verify'])} | "
            f"store {fmt(row['store'])} | pipe {fmt(row['pipeline'])}"
        )


if __name__ == "__main__":
    main()
