#!/usr/bin/env python3
"""
E2E Benchmark for In-Memory Key-Value Stores.
Compares:
1. Python dict (Baseline)
2. warm_logic_rs.SovereignKV (Rust In-Memory, Zero-Copy Optimized)
3. Redis (External Process, via 'redis' library if available)

Measures Ops/Sec and Latency (p50/p99) for SET and GET operations with 1MB payloads.
"""

import argparse
import secrets
import statistics
import sys
import time
from abc import ABC, abstractmethod

try:
    import warm_logic_rs
except ImportError:
    print("ERROR: warm_logic_rs not found. Please install the package.")
    sys.exit(1)

try:
    import redis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class BaseKV(ABC):
    @abstractmethod
    def name(self) -> str:
        """Name of the backend."""
        pass

    @abstractmethod
    def set(self, key: str, value: bytes) -> None:
        """Store bytes."""
        pass

    @abstractmethod
    def get(self, key: str) -> bytes | None:
        """Retrieve bytes."""
        pass

    def setup(self):
        """Optional setup."""
        pass

    def teardown(self):
        """Optional teardown."""
        pass


class PythonDictKV(BaseKV):
    def __init__(self):
        self._store = {}

    def name(self) -> str:
        return "Python Dict"

    def set(self, key: str, value: bytes) -> None:
        self._store[key] = value

    def get(self, key: str) -> bytes | None:
        return self._store.get(key)


class SovereignKV(BaseKV):
    def __init__(self):
        self._store = warm_logic_rs.SovereignKV()

    def name(self) -> str:
        return "SovereignKV (Rust)"

    def set(self, key: str, value: bytes) -> None:
        self._store.set_bytes(key, value)

    def get(self, key: str) -> bytes | None:
        return self._store.get_bytes(key)


class RedisKV(BaseKV):
    def __init__(self, host="localhost", port=6379):
        self._client = None
        self.host = host
        self.port = port

    def name(self) -> str:
        return f"Redis ({self.host}:{self.port})"

    def setup(self):
        if not HAS_REDIS:
            raise RuntimeError("Redis library not installed.")
        self._client = redis.Redis(host=self.host, port=self.port, db=0)
        try:
            self._client.ping()
        except redis.ConnectionError:
            self._client = None
            raise RuntimeError("Redis server not reachable.")

    def set(self, key: str, value: bytes) -> None:
        self._client.set(key, value)

    def get(self, key: str) -> bytes | None:
        return self._client.get(key)

    def teardown(self):
        if self._client:
            self._client.close()


def benchmark(backend: BaseKV, items: int, payload_size: int, repeats: int):
    print(f"\n--- Benchmarking: {backend.name()} ---")
    print(f"Items: {items}, Payload: {payload_size} bytes, Repeats: {repeats}")

    data = secrets.token_bytes(payload_size)
    keys = [f"key_{i}" for i in range(items)]

    # SET Benchmark
    latencies = []
    start_total = time.perf_counter()

    # Warmup
    backend.set("warmup", data)

    for _ in range(repeats):
        for k in keys:
            t0 = time.perf_counter_ns()
            backend.set(k, data)
            t1 = time.perf_counter_ns()
            latencies.append(t1 - t0)

    end_total = time.perf_counter()
    total_time = end_total - start_total
    ops_sec = (items * repeats) / total_time

    print(f"[SET] Ops/Sec: {ops_sec:,.2f}")
    print(f"      Latency p50: {statistics.median(latencies) / 1000:.2f} µs")
    print(
        f"      Latency p99: {statistics.quantiles(latencies, n=100)[98] / 1000:.2f} µs"
    )

    # GET Benchmark
    latencies = []
    start_total = time.perf_counter()

    # Warmup
    backend.get("warmup")

    for _ in range(repeats):
        for k in keys:
            t0 = time.perf_counter_ns()
            val = backend.get(k)
            t1 = time.perf_counter_ns()
            # Validation (cheap check)
            if val is not None and len(val) != payload_size:
                print("Error: content mismatch!")
            latencies.append(t1 - t0)

    end_total = time.perf_counter()
    total_time = end_total - start_total
    ops_sec = (items * repeats) / total_time

    print(f"[GET] Ops/Sec: {ops_sec:,.2f}")
    print(f"      Latency p50: {statistics.median(latencies) / 1000:.2f} µs")
    print(
        f"      Latency p99: {statistics.quantiles(latencies, n=100)[98] / 1000:.2f} µs"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=int, default=1000)
    parser.add_argument("--size", type=int, default=1024 * 1024)  # 1MB
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--skip-redis", action="store_true")
    args = parser.parse_args()

    backends = [PythonDictKV(), SovereignKV()]
    if not args.skip_redis:
        try:
            r = RedisKV()
            r.setup()
            backends.append(r)
        except RuntimeError as e:
            print(f"Skipping Redis: {e}")
        except Exception:
            print(f"Skipping Redis (Not installed or failed)")

    for b in backends:
        try:
            b.setup()
            benchmark(b, args.items, args.size, args.repeats)
        except Exception as e:
            print(f"Failed benchmark for {b.name()}: {e}")
        finally:
            b.teardown()


if __name__ == "__main__":
    main()
