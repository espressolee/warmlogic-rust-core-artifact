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
[Q4 2026] Performance Benchmark Infrastructure

Provides comprehensive benchmarking capabilities:
- Transaction throughput (TPS) measurement
- Latency percentile tracking (p50, p95, p99)
- Load generation and stress testing
- Performance regression detection
- Benchmark report generation
"""

from __future__ import annotations

import logging
import random
import statistics
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class BenchmarkStatus(Enum):
    """Benchmark execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LoadPattern(Enum):
    """Load generation patterns."""

    CONSTANT = "constant"  # Fixed rate
    RAMP = "ramp"  # Gradual increase
    SPIKE = "spike"  # Sudden burst
    WAVE = "wave"  # Sinusoidal pattern
    STEP = "step"  # Step increases


class LatencyUnit(Enum):
    """Latency measurement units."""

    NANOSECONDS = "ns"
    MICROSECONDS = "us"
    MILLISECONDS = "ms"
    SECONDS = "s"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TransactionResult:
    """Result of a single transaction."""

    tx_id: str = ""
    success: bool = True
    latency_ms: float = 0.0
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyMetrics:
    """Latency statistics."""

    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    median_ms: float = 0.0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    p999_ms: float = 0.0
    std_dev_ms: float = 0.0
    sample_count: int = 0

    @classmethod
    def from_samples(cls, latencies: list[float]) -> LatencyMetrics:
        """Calculate metrics from latency samples."""
        if not latencies:
            return cls()

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(p: float) -> float:
            k = (n - 1) * p
            f = int(k)
            c = f + 1 if f + 1 < n else f
            return sorted_latencies[f] + (k - f) * (
                sorted_latencies[c] - sorted_latencies[f]
            )

        return cls(
            min_ms=min(sorted_latencies),
            max_ms=max(sorted_latencies),
            mean_ms=statistics.mean(sorted_latencies),
            median_ms=statistics.median(sorted_latencies),
            p50_ms=percentile(0.50),
            p90_ms=percentile(0.90),
            p95_ms=percentile(0.95),
            p99_ms=percentile(0.99),
            p999_ms=percentile(0.999),
            std_dev_ms=statistics.stdev(sorted_latencies) if n > 1 else 0.0,
            sample_count=n,
        )


@dataclass
class ThroughputMetrics:
    """Throughput statistics."""

    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    duration_seconds: float = 0.0
    tps: float = 0.0  # Transactions per second
    tps_successful: float = 0.0
    success_rate: float = 0.0
    peak_tps: float = 0.0
    sustained_tps: float = 0.0


@dataclass
class BenchmarkConfig:
    """Benchmark configuration."""

    name: str = "default"
    target_tps: int = 1000
    duration_seconds: int = 60
    warmup_seconds: int = 10
    cooldown_seconds: int = 5
    num_threads: int = 10
    load_pattern: LoadPattern = LoadPattern.CONSTANT
    ramp_steps: int = 5
    timeout_ms: float = 5000.0
    collect_latency_histogram: bool = True
    measure_interval_seconds: float = 1.0


@dataclass
class BenchmarkResult:
    """Complete benchmark result."""

    benchmark_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    status: BenchmarkStatus = BenchmarkStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    throughput: ThroughputMetrics = field(default_factory=ThroughputMetrics)
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)
    error_summary: dict[str, int] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    passed_threshold: bool = False
    failure_reason: str = ""


# =============================================================================
# Transaction Generator
# =============================================================================


class TransactionGenerator(ABC):
    """Abstract base class for transaction generators."""

    @abstractmethod
    def generate(self) -> Callable[[], TransactionResult]:
        """Generate a transaction function."""
        pass

    @abstractmethod
    def name(self) -> str:
        """Return generator name."""
        pass


class SimpleTransactionGenerator(TransactionGenerator):
    """Simple transaction generator for testing."""

    def __init__(
        self,
        min_latency_ms: float = 1.0,
        max_latency_ms: float = 10.0,
        failure_rate: float = 0.001,
    ):
        self.min_latency_ms = min_latency_ms
        self.max_latency_ms = max_latency_ms
        self.failure_rate = failure_rate

    def name(self) -> str:
        return "simple"

    def generate(self) -> Callable[[], TransactionResult]:
        def transaction() -> TransactionResult:
            tx_id = str(uuid.uuid4())
            start = datetime.utcnow()
            start_time = time.perf_counter()

            # Simulate work
            latency = random.uniform(self.min_latency_ms, self.max_latency_ms)
            time.sleep(latency / 1000.0)

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            success = random.random() > self.failure_rate

            return TransactionResult(
                tx_id=tx_id,
                success=success,
                latency_ms=elapsed_ms,
                start_time=start,
                end_time=datetime.utcnow(),
                error_message="" if success else "Simulated failure",
            )

        return transaction


class CustomTransactionGenerator(TransactionGenerator):
    """Custom transaction generator with user-provided function."""

    def __init__(
        self,
        transaction_func: Callable[[], tuple[bool, str]],
        name: str = "custom",
    ):
        self._transaction_func = transaction_func
        self._name = name

    def name(self) -> str:
        return self._name

    def generate(self) -> Callable[[], TransactionResult]:
        def transaction() -> TransactionResult:
            tx_id = str(uuid.uuid4())
            start = datetime.utcnow()
            start_time = time.perf_counter()

            try:
                success, message = self._transaction_func()
                error = "" if success else message
            except Exception as e:
                success = False
                error = str(e)

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            return TransactionResult(
                tx_id=tx_id,
                success=success,
                latency_ms=elapsed_ms,
                start_time=start,
                end_time=datetime.utcnow(),
                error_message=error,
            )

        return transaction


# =============================================================================
# Load Generator
# =============================================================================


class _LoadGeneratorState:
    """Internal state for LoadGenerator.run() method."""

    def __init__(self, start_time: float) -> None:
        self.last_measure_time = start_time
        self.transactions_in_interval = 0
        self.interval_latencies: list[float] = []


class LoadGenerator:
    """
    Generates load according to specified pattern.

    Supports constant, ramp, spike, wave, and step patterns.
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        generator: TransactionGenerator,
    ):
        self.config = config
        self.generator = generator
        self._stop_event = threading.Event()
        self._results: deque[TransactionResult] = deque()
        self._lock = threading.Lock()
        self._timeline_data: list[dict[str, Any]] = []

    def _get_target_rate(self, elapsed_seconds: float) -> float:
        """Calculate target TPS based on load pattern and elapsed time."""
        target = float(self.config.target_tps)
        total_duration = (
            self.config.duration_seconds
            + self.config.warmup_seconds
            + self.config.cooldown_seconds
        )

        if self.config.load_pattern == LoadPattern.CONSTANT:
            return target

        elif self.config.load_pattern == LoadPattern.RAMP:
            # Linear ramp up
            ramp_factor = min(elapsed_seconds / self.config.warmup_seconds, 1.0)
            return target * ramp_factor

        elif self.config.load_pattern == LoadPattern.SPIKE:
            # 80% constant, then spike to 150% for 10%
            if elapsed_seconds < total_duration * 0.45:
                return target * 0.8
            elif elapsed_seconds < total_duration * 0.55:
                return target * 1.5
            else:
                return target * 0.8

        elif self.config.load_pattern == LoadPattern.WAVE:
            # Sinusoidal pattern
            import math

            amplitude = target * 0.3
            base = target * 0.7
            wave_period = total_duration / 3
            return base + amplitude * math.sin(
                2 * math.pi * elapsed_seconds / wave_period
            )

        elif self.config.load_pattern == LoadPattern.STEP:
            # Step increases
            step_duration = total_duration / self.config.ramp_steps
            current_step = min(
                int(elapsed_seconds / step_duration) + 1,
                self.config.ramp_steps,
            )
            return target * (current_step / self.config.ramp_steps)

        # Exhaustive match - should never reach here
        # All LoadPattern values are handled above
        raise ValueError(f"Unhandled load pattern: {self.config.load_pattern}")

    def _execute_transaction(self) -> TransactionResult | None:
        """Execute a single transaction."""
        if self._stop_event.is_set():
            return None

        tx_func = self.generator.generate()
        result = tx_func()

        with self._lock:
            self._results.append(result)

        return result

    def run(self) -> list[TransactionResult]:
        """
        Run the load generation.

        Returns:
            List of transaction results.
        """
        self._stop_event.clear()
        self._results.clear()
        self._timeline_data.clear()

        start_time = time.perf_counter()
        total_duration = (
            self.config.duration_seconds
            + self.config.warmup_seconds
            + self.config.cooldown_seconds
        )

        state = _LoadGeneratorState(start_time)

        with ThreadPoolExecutor(max_workers=self.config.num_threads) as executor:
            futures: list[Any] = []

            while not self._stop_event.is_set():
                elapsed = time.perf_counter() - start_time
                if elapsed >= total_duration:
                    break

                target_rate = self._get_target_rate(elapsed)
                self._submit_transactions(executor, futures, elapsed, target_rate)
                self._collect_results(futures, state)
                self._record_timeline(elapsed, target_rate, state)
                time.sleep(0.001)  # Prevent CPU spinning

            self._wait_for_futures(futures)

        return list(self._results)

    def _submit_transactions(
        self,
        executor: ThreadPoolExecutor,
        futures: list[Any],
        elapsed: float,
        target_rate: float,
    ) -> None:
        """Submit transactions to achieve target rate."""
        current_results_count = len(self._results)
        expected_transactions = target_rate * elapsed
        if current_results_count < expected_transactions:
            to_submit = min(
                int(expected_transactions - current_results_count) + 1,
                self.config.num_threads * 2,
            )
            for _ in range(to_submit):
                futures.append(executor.submit(self._execute_transaction))

    def _collect_results(
        self,
        futures: list[Any],
        state: "_LoadGeneratorState",
    ) -> None:
        """Collect completed futures."""
        ready_futures = [f for f in futures if f.done()]
        for f in ready_futures:
            try:
                result = f.result(timeout=0)
                if result:
                    state.transactions_in_interval += 1
                    state.interval_latencies.append(result.latency_ms)
            except Exception:
                pass
            futures.remove(f)

    def _record_timeline(
        self,
        elapsed: float,
        target_rate: float,
        state: "_LoadGeneratorState",
    ) -> None:
        """Record timeline data point if interval elapsed."""
        current_time = time.perf_counter()
        interval_elapsed = current_time - state.last_measure_time
        if interval_elapsed < self.config.measure_interval_seconds:
            return

        interval_tps = (
            state.transactions_in_interval / interval_elapsed
            if interval_elapsed > 0
            else 0
        )
        avg_latency = (
            round(sum(state.interval_latencies) / len(state.interval_latencies), 2)
            if state.interval_latencies
            else 0
        )

        self._timeline_data.append(
            {
                "timestamp": elapsed,
                "tps": round(interval_tps, 2),
                "target_tps": round(target_rate, 2),
                "transactions": state.transactions_in_interval,
                "avg_latency_ms": avg_latency,
            }
        )

        state.transactions_in_interval = 0
        state.interval_latencies = []
        state.last_measure_time = current_time

    def _wait_for_futures(self, futures: list[Any]) -> None:
        """Wait for remaining futures to complete."""
        for f in as_completed(futures, timeout=self.config.timeout_ms / 1000):
            try:
                f.result()
            except Exception:
                pass

    def stop(self) -> None:
        """Stop the load generation."""
        self._stop_event.set()

    def get_timeline(self) -> list[dict[str, Any]]:
        """Get timeline data."""
        return self._timeline_data


# =============================================================================
# Benchmark Runner
# =============================================================================


class BenchmarkRunner:
    """
    Executes benchmarks and collects results.

    Supports warmup, sustained load, and cooldown phases.
    """

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig()
        self._current_result: BenchmarkResult | None = None
        self._load_generator: LoadGenerator | None = None

    def run(
        self,
        generator: TransactionGenerator,
        threshold_tps: float | None = None,
    ) -> BenchmarkResult:
        """
        Run a benchmark.

        Args:
            generator: Transaction generator to use.
            threshold_tps: Minimum TPS required to pass.

        Returns:
            BenchmarkResult with metrics.
        """
        result = BenchmarkResult(config=self.config)
        result.status = BenchmarkStatus.RUNNING
        result.started_at = datetime.utcnow()

        try:
            self._load_generator = LoadGenerator(self.config, generator)
            tx_results = self._load_generator.run()

            # Calculate metrics
            result.throughput = self._calculate_throughput(tx_results)
            result.latency = self._calculate_latency(tx_results)
            result.error_summary = self._calculate_errors(tx_results)
            result.timeline = self._load_generator.get_timeline()

            # Check threshold
            if threshold_tps is not None:
                result.passed_threshold = result.throughput.tps >= threshold_tps
                if not result.passed_threshold:
                    result.failure_reason = f"TPS {result.throughput.tps:.2f} below threshold {threshold_tps}"

            result.status = BenchmarkStatus.COMPLETED

        except Exception as e:
            result.status = BenchmarkStatus.FAILED
            result.failure_reason = str(e)
            logger.error(f"Benchmark failed: {e}")

        result.completed_at = datetime.utcnow()
        self._current_result = result
        return result

    def _calculate_throughput(
        self,
        results: list[TransactionResult],
    ) -> ThroughputMetrics:
        """Calculate throughput metrics from results."""
        if not results:
            return ThroughputMetrics()

        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful

        # Calculate duration
        start_times = [r.start_time for r in results]
        end_times = [r.end_time for r in results if r.end_time]

        if start_times and end_times:
            duration = (max(end_times) - min(start_times)).total_seconds()
        else:
            duration = 0.0

        tps = total / duration if duration > 0 else 0.0
        tps_successful = successful / duration if duration > 0 else 0.0

        # Calculate peak TPS from timeline
        if self._load_generator:
            timeline = self._load_generator.get_timeline()
            peak_tps = max((t.get("tps", 0) for t in timeline), default=0)
            # Sustained is average of middle 80%
            if len(timeline) > 5:
                middle_start = len(timeline) // 10
                middle_end = len(timeline) - middle_start
                sustained = sum(
                    t.get("tps", 0) for t in timeline[middle_start:middle_end]
                ) / (middle_end - middle_start)
            else:
                sustained = tps
        else:
            peak_tps = tps
            sustained = tps

        return ThroughputMetrics(
            total_transactions=total,
            successful_transactions=successful,
            failed_transactions=failed,
            duration_seconds=duration,
            tps=round(tps, 2),
            tps_successful=round(tps_successful, 2),
            success_rate=successful / total if total > 0 else 0.0,
            peak_tps=round(peak_tps, 2),
            sustained_tps=round(sustained, 2),
        )

    def _calculate_latency(
        self,
        results: list[TransactionResult],
    ) -> LatencyMetrics:
        """Calculate latency metrics from results."""
        latencies = [r.latency_ms for r in results if r.success]
        return LatencyMetrics.from_samples(latencies)

    def _calculate_errors(
        self,
        results: list[TransactionResult],
    ) -> dict[str, int]:
        """Calculate error summary from results."""
        errors: dict[str, int] = {}
        for r in results:
            if not r.success and r.error_message:
                errors[r.error_message] = errors.get(r.error_message, 0) + 1
        return errors

    def cancel(self) -> None:
        """Cancel the running benchmark."""
        if self._load_generator:
            self._load_generator.stop()
        if self._current_result:
            self._current_result.status = BenchmarkStatus.CANCELLED


# =============================================================================
# Benchmark Suite
# =============================================================================


class BenchmarkSuite:
    """
    Collection of related benchmarks.

    Runs multiple benchmark configurations and aggregates results.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.benchmarks: dict[str, BenchmarkConfig] = {}
        self.results: dict[str, BenchmarkResult] = {}
        self._thresholds: dict[str, float] = {}

    def add_benchmark(
        self,
        name: str,
        config: BenchmarkConfig,
        threshold_tps: float | None = None,
    ) -> None:
        """Add a benchmark configuration."""
        self.benchmarks[name] = config
        if threshold_tps is not None:
            self._thresholds[name] = threshold_tps

    def run_all(
        self,
        generator: TransactionGenerator,
    ) -> dict[str, BenchmarkResult]:
        """Run all benchmarks in the suite."""
        self.results.clear()

        for name, config in self.benchmarks.items():
            logger.info(f"Running benchmark: {name}")
            runner = BenchmarkRunner(config)
            threshold = self._thresholds.get(name)
            result = runner.run(generator, threshold)
            self.results[name] = result
            logger.info(f"Benchmark {name} completed: TPS={result.throughput.tps}")

        return self.results

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all benchmark results."""
        if not self.results:
            return {"suite": self.name, "benchmarks": 0, "results": []}

        summaries = []
        all_passed = True

        for name, result in self.results.items():
            passed = (
                result.passed_threshold or result.status == BenchmarkStatus.COMPLETED
            )
            if not passed:
                all_passed = False

            summaries.append(
                {
                    "name": name,
                    "status": result.status.value,
                    "tps": result.throughput.tps,
                    "p99_ms": result.latency.p99_ms,
                    "success_rate": round(result.throughput.success_rate * 100, 2),
                    "passed": passed,
                }
            )

        return {
            "suite": self.name,
            "benchmarks": len(self.results),
            "all_passed": all_passed,
            "results": summaries,
            "completed_at": datetime.utcnow().isoformat(),
        }


# =============================================================================
# Performance Threshold Validator
# =============================================================================


@dataclass
class PerformanceThreshold:
    """Performance thresholds for validation."""

    min_tps: float = 1000.0
    max_p99_ms: float = 100.0
    max_p95_ms: float = 50.0
    min_success_rate: float = 0.999
    max_error_rate: float = 0.001


class ThresholdValidator:
    """
    Validates benchmark results against performance thresholds.

    Used for CI/CD gates and regression detection.
    """

    def __init__(self, threshold: PerformanceThreshold | None = None):
        self.threshold = threshold or PerformanceThreshold()

    def validate(self, result: BenchmarkResult) -> tuple[bool, list[str]]:
        """
        Validate benchmark result against thresholds.

        Returns:
            Tuple of (passed, list of violations).
        """
        violations = []

        # Check TPS
        if result.throughput.tps < self.threshold.min_tps:
            violations.append(
                f"TPS {result.throughput.tps} below minimum {self.threshold.min_tps}"
            )

        # Check P99 latency
        if result.latency.p99_ms > self.threshold.max_p99_ms:
            violations.append(
                f"P99 latency {result.latency.p99_ms}ms exceeds maximum {self.threshold.max_p99_ms}ms"
            )

        # Check P95 latency
        if result.latency.p95_ms > self.threshold.max_p95_ms:
            violations.append(
                f"P95 latency {result.latency.p95_ms}ms exceeds maximum {self.threshold.max_p95_ms}ms"
            )

        # Check success rate
        if result.throughput.success_rate < self.threshold.min_success_rate:
            violations.append(
                f"Success rate {result.throughput.success_rate:.4f} below minimum {self.threshold.min_success_rate}"
            )

        # Check error rate
        error_rate = 1 - result.throughput.success_rate
        if error_rate > self.threshold.max_error_rate:
            violations.append(
                f"Error rate {error_rate:.4f} exceeds maximum {self.threshold.max_error_rate}"
            )

        passed = len(violations) == 0
        return passed, violations


# =============================================================================
# Regression Detector
# =============================================================================


@dataclass
class BenchmarkBaseline:
    """Baseline metrics for regression detection."""

    name: str = ""
    tps: float = 0.0
    p99_ms: float = 0.0
    p95_ms: float = 0.0
    recorded_at: datetime = field(default_factory=datetime.utcnow)


class RegressionDetector:
    """
    Detects performance regressions against baseline.

    Compares current results to historical baselines.
    """

    def __init__(self, tolerance_percent: float = 10.0):
        self.tolerance = tolerance_percent / 100.0
        self.baselines: dict[str, BenchmarkBaseline] = {}

    def set_baseline(
        self,
        name: str,
        tps: float,
        p99_ms: float,
        p95_ms: float,
    ) -> BenchmarkBaseline:
        """Set a baseline for comparison."""
        baseline = BenchmarkBaseline(
            name=name,
            tps=tps,
            p99_ms=p99_ms,
            p95_ms=p95_ms,
        )
        self.baselines[name] = baseline
        return baseline

    def check_regression(
        self,
        name: str,
        result: BenchmarkResult,
    ) -> tuple[bool, list[str]]:
        """
        Check if result shows regression from baseline.

        Returns:
            Tuple of (has_regression, list of regressions).
        """
        baseline = self.baselines.get(name)
        if not baseline:
            return False, []

        regressions = []

        # Check TPS regression (lower is worse)
        tps_change = (baseline.tps - result.throughput.tps) / baseline.tps
        if tps_change > self.tolerance:
            regressions.append(
                f"TPS regression: {result.throughput.tps:.2f} vs baseline {baseline.tps:.2f} (-{tps_change*100:.1f}%)"
            )

        # Check P99 regression (higher is worse)
        if baseline.p99_ms > 0:
            p99_change = (result.latency.p99_ms - baseline.p99_ms) / baseline.p99_ms
            if p99_change > self.tolerance:
                regressions.append(
                    f"P99 regression: {result.latency.p99_ms:.2f}ms vs baseline {baseline.p99_ms:.2f}ms (+{p99_change*100:.1f}%)"
                )

        # Check P95 regression (higher is worse)
        if baseline.p95_ms > 0:
            p95_change = (result.latency.p95_ms - baseline.p95_ms) / baseline.p95_ms
            if p95_change > self.tolerance:
                regressions.append(
                    f"P95 regression: {result.latency.p95_ms:.2f}ms vs baseline {baseline.p95_ms:.2f}ms (+{p95_change*100:.1f}%)"
                )

        return len(regressions) > 0, regressions


# =============================================================================
# Report Generator
# =============================================================================


class BenchmarkReportGenerator:
    """Generates benchmark reports in various formats."""

    def generate_text_report(self, result: BenchmarkResult) -> str:
        """Generate a text report."""
        lines = [
            "=" * 60,
            f"Benchmark Report: {result.config.name}",
            "=" * 60,
            "",
            f"Status: {result.status.value}",
            f"Started: {result.started_at}",
            f"Completed: {result.completed_at}",
            "",
            "Throughput Metrics:",
            f"  Total Transactions: {result.throughput.total_transactions:,}",
            f"  Successful: {result.throughput.successful_transactions:,}",
            f"  Failed: {result.throughput.failed_transactions:,}",
            f"  Duration: {result.throughput.duration_seconds:.2f}s",
            f"  TPS: {result.throughput.tps:.2f}",
            f"  Peak TPS: {result.throughput.peak_tps:.2f}",
            f"  Sustained TPS: {result.throughput.sustained_tps:.2f}",
            f"  Success Rate: {result.throughput.success_rate*100:.2f}%",
            "",
            "Latency Metrics:",
            f"  Min: {result.latency.min_ms:.2f}ms",
            f"  Max: {result.latency.max_ms:.2f}ms",
            f"  Mean: {result.latency.mean_ms:.2f}ms",
            f"  P50: {result.latency.p50_ms:.2f}ms",
            f"  P90: {result.latency.p90_ms:.2f}ms",
            f"  P95: {result.latency.p95_ms:.2f}ms",
            f"  P99: {result.latency.p99_ms:.2f}ms",
            f"  P99.9: {result.latency.p999_ms:.2f}ms",
            "",
        ]

        if result.error_summary:
            lines.append("Error Summary:")
            for error, count in result.error_summary.items():
                lines.append(f"  {error}: {count}")
            lines.append("")

        if result.failure_reason:
            lines.append(f"Failure Reason: {result.failure_reason}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def generate_json_report(self, result: BenchmarkResult) -> dict[str, Any]:
        """Generate a JSON-compatible report."""
        return {
            "benchmark_id": result.benchmark_id,
            "config": {
                "name": result.config.name,
                "target_tps": result.config.target_tps,
                "duration_seconds": result.config.duration_seconds,
                "load_pattern": result.config.load_pattern.value,
                "num_threads": result.config.num_threads,
            },
            "status": result.status.value,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": (
                result.completed_at.isoformat() if result.completed_at else None
            ),
            "throughput": {
                "total_transactions": result.throughput.total_transactions,
                "successful_transactions": result.throughput.successful_transactions,
                "failed_transactions": result.throughput.failed_transactions,
                "duration_seconds": result.throughput.duration_seconds,
                "tps": result.throughput.tps,
                "tps_successful": result.throughput.tps_successful,
                "success_rate": result.throughput.success_rate,
                "peak_tps": result.throughput.peak_tps,
                "sustained_tps": result.throughput.sustained_tps,
            },
            "latency": {
                "min_ms": result.latency.min_ms,
                "max_ms": result.latency.max_ms,
                "mean_ms": result.latency.mean_ms,
                "median_ms": result.latency.median_ms,
                "p50_ms": result.latency.p50_ms,
                "p90_ms": result.latency.p90_ms,
                "p95_ms": result.latency.p95_ms,
                "p99_ms": result.latency.p99_ms,
                "p999_ms": result.latency.p999_ms,
                "std_dev_ms": result.latency.std_dev_ms,
                "sample_count": result.latency.sample_count,
            },
            "error_summary": result.error_summary,
            "timeline": result.timeline,
            "passed_threshold": result.passed_threshold,
            "failure_reason": result.failure_reason,
        }
