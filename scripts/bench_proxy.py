import hashlib
import sys
import time


def benchmark_sha3():
    data = b"\xab" * 168  # 168 bytes
    iterations = 10000

    start_time = time.perf_counter()
    for _ in range(iterations):
        h = hashlib.sha3_256()
        h.update(data)
        _ = h.digest()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    avg_time_us = (total_time * 1_000_000) / iterations

    print(f"SHA3-256 (168 bytes): {avg_time_us:.2f} us/op")
    return avg_time_us


if __name__ == "__main__":
    print(f"Benchmarking on {sys.platform}...")
    benchmark_sha3()
