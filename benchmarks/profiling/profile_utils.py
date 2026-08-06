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
Performance profiling utilities for WarmLogic kernel.

Provides:
- Function-level profiling with cProfile
- Memory profiling with tracemalloc
- Benchmark result aggregation
- Statistical analysis of performance metrics
"""

import cProfile
import gc
import io
import pstats
import statistics
import sys
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    iterations: int
    total_time_sec: float
    min_time_sec: float
    max_time_sec: float
    mean_time_sec: float
    median_time_sec: float
    std_dev_sec: float
    memory_peak_mb: float = 0.0
    memory_avg_mb: float = 0.0
    throughput: float = 0.0  # ops/sec
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    extra_metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def latency_avg_ms(self) -> float:
        return self.mean_time_sec * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_sec": round(self.total_time_sec, 6),
            "throughput_ops_sec": round(self.throughput, 2),
            "latency_avg_ms": round(self.latency_avg_ms, 3),
            "latency_p50_ms": round(self.latency_p50_ms, 3),
            "latency_p95_ms": round(self.latency_p95_ms, 3),
            "latency_p99_ms": round(self.latency_p99_ms, 3),
            "memory_peak_mb": round(self.memory_peak_mb, 2),
            "std_dev_sec": round(self.std_dev_sec, 6),
            **self.extra_metrics,
        }

    def summary(self) -> str:
        lines = [
            f"📊 {self.name}",
            f"   Iterations: {self.iterations}",
            f"   Throughput: {self.throughput:.2f} ops/sec",
            f"   Latency:    p50={self.latency_p50_ms:.2f}ms, p95={self.latency_p95_ms:.2f}ms, p99={self.latency_p99_ms:.2f}ms",
            f"   Memory:     peak={self.memory_peak_mb:.2f}MB",
        ]
        return "\n".join(lines)


class MemoryProfiler:
    """Memory profiling context manager using tracemalloc."""

    def __init__(self, sample_interval_sec: float = 0.1):
        self.sample_interval = sample_interval_sec
        self.samples: List[int] = []
        self.peak_bytes: int = 0
        self._start_snapshot: Optional[tracemalloc.Snapshot] = None

    def start(self) -> None:
        gc.collect()
        tracemalloc.start()
        self._start_snapshot = tracemalloc.take_snapshot()

    def sample(self) -> int:
        """Take a memory sample. Returns current memory in bytes."""
        current, peak = tracemalloc.get_traced_memory()
        self.samples.append(current)
        self.peak_bytes = max(self.peak_bytes, peak)
        return current

    def stop(self) -> Tuple[float, float]:
        """Stop profiling. Returns (peak_mb, avg_mb)."""
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            self.peak_bytes = max(self.peak_bytes, peak)
            tracemalloc.stop()

        peak_mb = self.peak_bytes / (1024 * 1024)
        avg_mb = 0.0
        if self.samples:
            avg_mb = statistics.mean(self.samples) / (1024 * 1024)

        return peak_mb, avg_mb

    def get_top_allocations(self, limit: int = 10) -> List[str]:
        """Get top memory allocations from start snapshot comparison."""
        if not tracemalloc.is_tracing():
            return []

        end_snapshot = tracemalloc.take_snapshot()
        if self._start_snapshot is None:
            return []

        top_stats = end_snapshot.compare_to(
            self._start_snapshot, "lineno", cumulative=True
        )
        return [str(stat) for stat in top_stats[:limit]]


def profile_function(
    func: Callable,
    *args,
    iterations: int = 100,
    warmup: int = 10,
    track_memory: bool = True,
    **kwargs,
) -> BenchmarkResult:
    """
    Profile a function with statistical analysis.

    Args:
        func: Function to profile
        iterations: Number of iterations to run
        warmup: Warmup iterations (not counted in results)
        track_memory: Whether to track memory usage
        *args, **kwargs: Arguments to pass to function

    Returns:
        BenchmarkResult with detailed metrics
    """
    name = func.__name__

    # Warmup
    for _ in range(warmup):
        func(*args, **kwargs)

    # Memory profiler
    mem_profiler = MemoryProfiler() if track_memory else None
    if mem_profiler:
        mem_profiler.start()

    # Benchmark
    times = []
    gc.collect()

    for i in range(iterations):
        start = time.perf_counter()
        func(*args, **kwargs)
        end = time.perf_counter()
        times.append(end - start)

        if mem_profiler and i % 10 == 0:
            mem_profiler.sample()

    # Memory results
    peak_mb, avg_mb = (0.0, 0.0)
    if mem_profiler:
        peak_mb, avg_mb = mem_profiler.stop()

    # Statistical analysis
    sorted_times = sorted(times)
    total_time = sum(times)

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_time_sec=total_time,
        min_time_sec=min(times),
        max_time_sec=max(times),
        mean_time_sec=statistics.mean(times),
        median_time_sec=statistics.median(times),
        std_dev_sec=statistics.stdev(times) if len(times) > 1 else 0.0,
        memory_peak_mb=peak_mb,
        memory_avg_mb=avg_mb,
        throughput=iterations / total_time,
        latency_p50_ms=sorted_times[int(len(sorted_times) * 0.5)] * 1000,
        latency_p95_ms=sorted_times[int(len(sorted_times) * 0.95)] * 1000,
        latency_p99_ms=sorted_times[int(len(sorted_times) * 0.99)] * 1000,
    )


@contextmanager
def run_with_profiler(output_lines: int = 30):
    """
    Context manager for cProfile profiling.

    Usage:
        with run_with_profiler() as prof:
            # code to profile
        # profile stats are printed automatically
    """
    profiler = cProfile.Profile()
    profiler.enable()

    try:
        yield profiler
    finally:
        profiler.disable()

        # Print stats
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative")
        stats.print_stats(output_lines)
        print(stream.getvalue())


class BenchmarkSuite:
    """
    Suite for running and collecting multiple benchmarks.

    Usage:
        suite = BenchmarkSuite("Kernel Performance")
        suite.add("consensus", consensus_benchmark, iterations=100)
        suite.add("crypto", crypto_benchmark, iterations=1000)
        results = suite.run()
        suite.print_report()
    """

    def __init__(self, name: str):
        self.name = name
        self.benchmarks: List[Tuple[str, Callable, Dict[str, Any]]] = []
        self.results: List[BenchmarkResult] = []

    def add(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10,
        **kwargs,
    ) -> "BenchmarkSuite":
        """Add a benchmark to the suite."""
        self.benchmarks.append(
            (name, func, {"iterations": iterations, "warmup": warmup, **kwargs})
        )
        return self

    def run(self, verbose: bool = True) -> List[BenchmarkResult]:
        """Run all benchmarks in the suite."""
        if verbose:
            print(f"\n{'='*60}")
            print(f"🏃 Running Benchmark Suite: {self.name}")
            print(f"{'='*60}\n")

        self.results = []

        for name, func, kwargs in self.benchmarks:
            if verbose:
                print(f"⏱️  {name}...")

            result = profile_function(func, **kwargs)
            result.name = name  # Override with suite name
            self.results.append(result)

            if verbose:
                print(
                    f"    ✅ {result.throughput:.2f} ops/sec, p99={result.latency_p99_ms:.2f}ms\n"
                )

        return self.results

    def print_report(self) -> None:
        """Print a formatted report of all results."""
        print(f"\n{'='*60}")
        print(f"📊 BENCHMARK REPORT: {self.name}")
        print(f"{'='*60}\n")

        for result in self.results:
            print(result.summary())
            print()

        # Summary table
        print(f"{'─'*60}")
        print(
            f"{'Benchmark':<30} {'Throughput':>12} {'p99 Latency':>12} {'Peak Mem':>10}"
        )
        print(f"{'─'*60}")
        for r in self.results:
            print(
                f"{r.name:<30} {r.throughput:>10.2f}/s {r.latency_p99_ms:>10.2f}ms {r.memory_peak_mb:>8.2f}MB"
            )
        print(f"{'─'*60}")

    def to_json(self) -> List[Dict[str, Any]]:
        """Export results as JSON-serializable list."""
        return [r.to_dict() for r in self.results]
