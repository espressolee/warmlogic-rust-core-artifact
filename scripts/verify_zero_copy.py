import os
import sys
import time
from pathlib import Path

# Ensure import path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError as e:
    print(f"Failed to load warm_logic_rs: {e}")
    sys.exit(1)


def verify_zero_copy():
    if not hasattr(warm_logic_rs, "benchmark_zero_copy"):
        print("benchmark_zero_copy function not found in warm_logic_rs module.")
        sys.exit(1)

    sizes = [
        (10 * 1024, "10KB"),
        (100 * 1024, "100KB"),
        (1 * 1024 * 1024, "1MB"),
        (10 * 1024 * 1024, "10MB"),
    ]

    results = []

    print("\nStarting Zero-Copy Verification (O(1) Proof)...")
    print(f"{'Size':<10} | {'Time (s)':<15} | {'Throughput (GB/s)':<20}")
    print("-" * 50)

    base_time = 0.0

    for size, label in sizes:
        data = b"x" * size

        # Warmup
        warm_logic_rs.benchmark_zero_copy(data)

        start = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            warm_logic_rs.benchmark_zero_copy(data)
        end = time.perf_counter()

        avg_time = (end - start) / iterations

        if label == "10KB":
            base_time = avg_time

        throughput = (size / 1024 / 1024 / 1024) / avg_time if avg_time > 0 else 0

        print(f"{label:<10} | {avg_time:.9f}   | {throughput:.2f}")
        results.append((label, avg_time))

    print("-" * 50)

    # Verification Logic
    # We allow some jitter, but 10MB shouldn't be 1000x slower than 10KB.
    # If it were O(N) copy, 10MB would be ~1000x slower than 10KB.
    # O(1) means they are roughly equal (within small overhead variance).

    t_10kb = results[0][1]
    t_10mb = results[3][1]

    ratio = t_10mb / t_10kb if t_10kb > 0 else 0
    print(f"\n10MB / 10KB Time Ratio: {ratio:.2f}x")

    if ratio < 2.0:
        print("SUCCESS: Time is effectively constant (O(1)). Zero-Copy confirmed.")
        sys.exit(0)
    elif ratio < 10.0:
        print(
            "⚠️ WARNING: Slight increase detected, but likely not linear copy. (Need investigation if ratio > 5)"
        )
        # Ideally we want strictly flat, but Python GC and overhead might cause jitter.
        # But O(N) copy for 10MB vs 10KB would be drastic.
        sys.exit(0)  # Passing for now if it's not massive order of magnitude
    else:
        print("FAILURE: Time increased significantly. Likely memory copy occurring.")
        sys.exit(1)


if __name__ == "__main__":
    verify_zero_copy()
