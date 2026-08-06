#!/usr/bin/env python3
"""
End-to-End Benchmark: Sovereign Message Sign-Verify-Store Pipeline

This benchmark measures a realistic workload that crosses the Python↔Rust
boundary multiple times per operation:
  1. Generate keypair (Rust)
  2. Sign message content (Rust)
  3. Verify signature (Rust)
  4. Store to SovereignStore (Rust/Sled)

This represents an actual WarmLogic usage pattern, not just microbenchmarks.
"""

import gc
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import List

# Import strategy (match eval_bridge_v3.py):
use_installed = os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1"
ext_path = os.environ.get("WARM_LOGIC_RS_PYTHON_PATH")
repo_root = os.getcwd()
if not use_installed:
    ext_path = ext_path or os.path.join(
        repo_root, "warm_logic_rs", "python_packages_v2"
    )
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


@dataclass
class BenchmarkConfig:
    message_sizes: List[int] = None  # bytes
    iterations: int = 100
    warmup: int = 20
    run_id: str = "e2e_sovereign_pipeline"

    def __post_init__(self):
        if self.message_sizes is None:
            self.message_sizes = [100, 1_000, 10_000, 100_000]


def generate_message_content(size: int) -> str:
    """Generate a message of approximately the given size."""
    base = "WarmLogic Sovereign Message Content - "
    repeat_count = max(1, size // len(base))
    return (base * repeat_count)[:size]


def benchmark_sign_only(
    private_key: str, messages: List[str], iterations: int
) -> float:
    """Measure sign-only latency."""
    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        for msg in messages:
            _ = warm_logic_rs.sign(private_key, msg)
    end = time.perf_counter_ns()
    gc.enable()
    return (end - start) / (iterations * len(messages))


def benchmark_verify_only(
    public_key: str, messages: List[str], signatures: List[str], iterations: int
) -> float:
    """Measure verify-only latency."""
    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        for msg, sig in zip(messages, signatures):
            _ = warm_logic_rs.verify(public_key, msg, sig)
    end = time.perf_counter_ns()
    gc.enable()
    return (end - start) / (iterations * len(messages))


def benchmark_store_put(
    store, signatures: List[str], json_payloads: List[str], iterations: int
) -> float:
    """Measure store put latency (includes Sled write)."""
    gc.disable()
    start = time.perf_counter_ns()
    for i in range(iterations):
        for sig, payload in zip(signatures, json_payloads):
            # Use unique keys to avoid collision
            unique_key = f"{sig}_{i}"
            store.put(unique_key, payload)
    end = time.perf_counter_ns()
    gc.enable()
    return (end - start) / (iterations * len(signatures))


def benchmark_full_pipeline(
    public_key: str, private_key: str, store, messages: List[str], iterations: int
) -> float:
    """Measure full sign→verify→store pipeline."""
    gc.disable()
    start = time.perf_counter_ns()
    for i in range(iterations):
        for msg in messages:
            # 1. Sign
            sig = warm_logic_rs.sign(private_key, msg)
            # 2. Verify
            is_valid = warm_logic_rs.verify(public_key, msg, sig)
            # 3. Store (if valid)
            if is_valid:
                payload = json.dumps({"content": msg, "sig": sig})
                store.put(f"{sig}_{i}", payload)
    end = time.perf_counter_ns()
    gc.enable()
    return (end - start) / (iterations * len(messages))


def run_benchmark(config: BenchmarkConfig) -> dict:
    """Run the full E2E benchmark suite."""
    results = {
        "metadata": {
            "run_id": config.run_id,
            "timestamp": time.time(),
            "iterations": config.iterations,
            "warmup": config.warmup,
            "message_sizes": config.message_sizes,
            "platform": sys.platform,
            "python": sys.version,
        },
        "results": [],
    }

    # Generate keypair once
    public_key, private_key = warm_logic_rs.generate_keypair()
    print(f"Generated keypair: {public_key[:20]}...")

    # Create temporary store
    tmp_dir = tempfile.mkdtemp(prefix="e2e_bench_")
    store = warm_logic_rs.SovereignStore(os.path.join(tmp_dir, "bench_db"))

    try:
        for msg_size in config.message_sizes:
            print(f"\n=== Message Size: {msg_size} bytes ===")

            # Prepare messages
            messages = [generate_message_content(msg_size) for _ in range(10)]

            # Pre-sign for verify-only and store benchmarks
            signatures = [warm_logic_rs.sign(private_key, m) for m in messages]
            json_payloads = [
                json.dumps({"content": m, "sig": s})
                for m, s in zip(messages, signatures)
            ]

            # Warmup
            print(f"  Warmup ({config.warmup} iterations)...")
            for _ in range(config.warmup):
                for m in messages:
                    sig = warm_logic_rs.sign(private_key, m)
                    _ = warm_logic_rs.verify(public_key, m, sig)

            # Benchmark: Sign only
            sign_ns = benchmark_sign_only(private_key, messages, config.iterations)
            print(f"  Sign only:       {sign_ns / 1000:.2f} µs/op")

            # Benchmark: Verify only
            verify_ns = benchmark_verify_only(
                public_key, messages, signatures, config.iterations
            )
            print(f"  Verify only:     {verify_ns / 1000:.2f} µs/op")

            # Benchmark: Store put only
            store_ns = benchmark_store_put(
                store, signatures, json_payloads, config.iterations
            )
            print(f"  Store put:       {store_ns / 1000:.2f} µs/op")

            # Benchmark: Full pipeline
            pipeline_ns = benchmark_full_pipeline(
                public_key, private_key, store, messages, config.iterations
            )
            print(f"  Full pipeline:   {pipeline_ns / 1000:.2f} µs/op")

            # Expected vs actual
            expected_sum = sign_ns + verify_ns + store_ns
            overhead_pct = (
                ((pipeline_ns - expected_sum) / expected_sum) * 100
                if expected_sum > 0
                else 0
            )
            print(f"  Pipeline overhead: {overhead_pct:.1f}% (vs sum of parts)")

            results["results"].append(
                {
                    "message_size_bytes": msg_size,
                    "sign_ns": sign_ns,
                    "verify_ns": verify_ns,
                    "store_ns": store_ns,
                    "pipeline_ns": pipeline_ns,
                    "overhead_pct": overhead_pct,
                }
            )

    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="E2E Sovereign Pipeline Benchmark")
    parser.add_argument("--run-id", default="e2e_sovereign_pipeline")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=20)
    args = parser.parse_args()

    config = BenchmarkConfig(
        run_id=args.run_id,
        iterations=args.iterations,
        warmup=args.warmup,
    )

    print("=" * 60)
    print("  E2E Benchmark: Sovereign Message Pipeline")
    print("=" * 60)

    results = run_benchmark(config)

    # Save results
    out_dir = f"out/bridge_eval/{config.run_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "e2e_telemetry.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote: {out_path}")

    # Summary table
    print("\n" + "=" * 60)
    print("  Summary (µs/operation)")
    print("=" * 60)
    print(
        f"{'Size':>10} | {'Sign':>10} | {'Verify':>10} | {'Store':>10} | {'Pipeline':>10} | {'Overhead':>8}"
    )
    print("-" * 70)
    for r in results["results"]:
        print(
            f"{r['message_size_bytes']:>10} | {r['sign_ns'] / 1000:>10.2f} | {r['verify_ns'] / 1000:>10.2f} | {r['store_ns'] / 1000:>10.2f} | {r['pipeline_ns'] / 1000:>10.2f} | {r['overhead_pct']:>7.1f}%"
        )


if __name__ == "__main__":
    main()
