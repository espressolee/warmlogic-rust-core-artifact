# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Memory profiling benchmarks for WarmLogic.

Analyzes memory usage patterns for:
- Governance state storage
- Cryptographic operations
- Consensus structures
- Caching behavior
"""

import gc
import os
import sys
import tracemalloc
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


@dataclass
class MemoryReport:
    """Memory usage report."""

    name: str
    peak_mb: float
    current_mb: float
    object_count: int
    top_allocations: List[str]

    def summary(self) -> str:
        lines = [
            f"📊 Memory Report: {self.name}",
            f"   Peak:     {self.peak_mb:.2f} MB",
            f"   Current:  {self.current_mb:.2f} MB",
            f"   Objects:  {self.object_count:,}",
            f"   Top Allocations:",
        ]
        for alloc in self.top_allocations[:5]:
            lines.append(f"     - {alloc}")
        return "\n".join(lines)


def profile_memory(name: str, setup_fn, iterations: int = 100) -> MemoryReport:
    """
    Profile memory usage of a function.

    Args:
        name: Name of the benchmark
        setup_fn: Function that creates/allocates objects
        iterations: Number of iterations to run

    Returns:
        MemoryReport with detailed memory analysis
    """
    gc.collect()
    tracemalloc.start()

    # Run iterations
    objects = []
    for _ in range(iterations):
        obj = setup_fn()
        objects.append(obj)

    # Take snapshot
    snapshot = tracemalloc.take_snapshot()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Get top allocations
    top_stats = snapshot.statistics("lineno")[:10]
    top_allocs = [
        f"{stat.traceback.format()[0]}: {stat.size / 1024:.1f} KB" for stat in top_stats
    ]

    # Count objects
    object_count = sum(1 for _ in gc.get_objects())

    # Clean up
    del objects
    gc.collect()

    return MemoryReport(
        name=name,
        peak_mb=peak / (1024 * 1024),
        current_mb=current / (1024 * 1024),
        object_count=object_count,
        top_allocations=top_allocs,
    )


def bench_governance_state_memory():
    """Benchmark memory usage of governance state structures."""

    def create_state():
        return {
            "epoch": 1000,
            "block_height": 50000,
            "decisions": [
                {
                    "id": f"decision-{i}",
                    "status": "approved",
                    "timestamp": 1700000000 + i,
                    "votes": [{"voter": f"v-{j}", "weight": 1.0} for j in range(5)],
                }
                for i in range(100)
            ],
            "validators": [
                {"id": f"validator-{i}", "stake": 10000, "region": f"region-{i%5}"}
                for i in range(100)
            ],
        }

    return profile_memory("governance_state", create_state, iterations=50)


def bench_crypto_buffer_memory():
    """Benchmark memory usage of cryptographic buffers."""

    def create_crypto_buffers():
        return {
            "public_keys": [os.urandom(1952) for _ in range(10)],  # ML-DSA-65 PK size
            "signatures": [os.urandom(3309) for _ in range(10)],  # ML-DSA-65 sig size
            "hashes": [os.urandom(32) for _ in range(100)],
        }

    return profile_memory("crypto_buffers", create_crypto_buffers, iterations=100)


def bench_consensus_vote_memory():
    """Benchmark memory usage of consensus vote structures."""

    @dataclass
    class MockVote:
        block_hash: str
        voter_id: str
        region: str
        decision: str
        signature: bytes
        timestamp: float

    def create_votes():
        return [
            MockVote(
                block_hash=f"block-{os.urandom(16).hex()}",
                voter_id=f"voter-{i}",
                region=f"region-{i%5}",
                decision="APPROVE",
                signature=os.urandom(3309),
                timestamp=1700000000.0,
            )
            for i in range(100)
        ]

    return profile_memory("consensus_votes", create_votes, iterations=50)


def bench_cache_memory():
    """Benchmark memory usage of caching structures."""

    class LRUCache:
        def __init__(self, capacity: int):
            self.capacity = capacity
            self.cache: Dict[str, Any] = {}
            self.order: List[str] = []

        def put(self, key: str, value: Any):
            if key in self.cache:
                self.order.remove(key)
            elif len(self.cache) >= self.capacity:
                oldest = self.order.pop(0)
                del self.cache[oldest]
            self.cache[key] = value
            self.order.append(key)

    def create_cache():
        cache = LRUCache(1000)
        for i in range(1000):
            cache.put(f"key-{i}", {"data": os.urandom(1024), "metadata": {"id": i}})
        return cache

    return profile_memory("lru_cache", create_cache, iterations=10)


def bench_federation_state_memory():
    """Benchmark memory usage of federation state."""

    def create_federation_state():
        return {
            "regions": {
                f"region-{i}": {
                    "nodes": [
                        {
                            "id": f"node-{j}",
                            "public_key": os.urandom(1952).hex(),
                            "last_seen": 1700000000,
                        }
                        for j in range(10)
                    ],
                    "health": {"is_healthy": True, "latency_ms": 50.0},
                }
                for i in range(7)
            },
            "pending_syncs": [
                {"id": f"sync-{i}", "decisions": [f"d-{j}" for j in range(10)]}
                for i in range(50)
            ],
        }

    return profile_memory("federation_state", create_federation_state, iterations=20)


def run_memory_benchmarks():
    """Run all memory benchmarks."""
    print("\n" + "=" * 60)
    print("🧠 WarmLogic Memory Profiling")
    print("=" * 60 + "\n")

    benchmarks = [
        bench_governance_state_memory,
        bench_crypto_buffer_memory,
        bench_consensus_vote_memory,
        bench_cache_memory,
        bench_federation_state_memory,
    ]

    reports = []
    for bench_fn in benchmarks:
        print(f"⏱️  Running {bench_fn.__name__}...")
        report = bench_fn()
        reports.append(report)
        print(f"    ✅ Peak: {report.peak_mb:.2f} MB\n")

    # Print summary
    print("\n" + "=" * 60)
    print("📊 MEMORY PROFILING REPORT")
    print("=" * 60 + "\n")

    for report in reports:
        print(report.summary())
        print()

    # Summary table
    print("─" * 60)
    print(f"{'Benchmark':<30} {'Peak MB':>12} {'Current MB':>12} {'Objects':>12}")
    print("─" * 60)
    for r in reports:
        print(
            f"{r.name:<30} {r.peak_mb:>10.2f} MB {r.current_mb:>10.2f} MB {r.object_count:>10,}"
        )
    print("─" * 60)

    # Total
    total_peak = sum(r.peak_mb for r in reports)
    print(f"{'TOTAL':<30} {total_peak:>10.2f} MB")

    return reports


if __name__ == "__main__":
    run_memory_benchmarks()
