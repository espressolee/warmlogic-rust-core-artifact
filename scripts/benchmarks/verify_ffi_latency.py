import sys
import time
import timeit

import warm_logic_rs


def verify_latency():
    print("=== verification Zero-Copy Verification ===")

    # payload = 1MB of data
    data = b"x" * 1_000_000

    # 1. Zero-Copy (O(1))
    # We want to measure the call overhead, not just the function body.
    # rust function: fn benchmark_zero_copy(data: &Bound<'_, pyo3::types::PyBytes>) -> usize

    ITERATIONS = 100_000

    t0 = time.perf_counter_ns()
    for _ in range(ITERATIONS):
        warm_logic_rs.benchmark_zero_copy(data)
    t1 = time.perf_counter_ns()

    total_ns = t1 - t0
    avg_ns = total_ns / ITERATIONS

    print(f"Payload: 1MB")
    print(f"Iterations: {ITERATIONS}")
    print(f"Total Time: {total_ns / 1e9:.4f}s")
    print(f"Average Latency (Zero-Copy): {avg_ns:.2f} ns/call")

    # Validation against Canon
    params = {"target": 250.0, "measured": avg_ns}

    if avg_ns < 250.0:
        print(f"PASS: Latency {avg_ns:.2f}ns < 250ns")
        return True
    else:
        print(f"FAIL: Latency {avg_ns:.2f}ns > 250ns")
        return False


def verify_copy_penalty():
    # 2. Forced Copy (O(N))
    # rust function: fn benchmark_copy_bridge
    data = b"x" * 1_000_000  # 1MB
    ITERATIONS = 100

    t0 = time.perf_counter_ns()
    for _ in range(ITERATIONS):
        warm_logic_rs.benchmark_copy_bridge(data)
    t1 = time.perf_counter_ns()

    avg_ns = (t1 - t0) / ITERATIONS
    print(
        f"Average Latency (Forced Copy 1MB): {avg_ns:.2f} ns/call ({avg_ns / 1e6:.2f} ms)"
    )

    # 3. Consumer Touch (O(N) Verified)
    t0 = time.perf_counter_ns()
    # Fewer iterations for partial O(N)
    ITERATIONS_N = 1000
    for _ in range(ITERATIONS_N):
        warm_logic_rs.benchmark_consume_bridge(data)
    t1 = time.perf_counter_ns()

    avg_consume_ns = (t1 - t0) / ITERATIONS_N
    print(
        f"Average Latency (Consume 1MB): {avg_consume_ns:.2f} ns/call ({avg_consume_ns / 1e6:.2f} ms)"
    )

    # Calculate Throughput
    gb_per_sec = (1_000_000 / (avg_consume_ns * 1e-9)) / 1e9
    print(f"Effective Throughput: {gb_per_sec:.2f} GB/s")


if __name__ == "__main__":
    if verify_latency():
        verify_copy_penalty()
        sys.exit(0)
    else:
        sys.exit(1)
