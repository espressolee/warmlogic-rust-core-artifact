"""Tests for Benchmark module."""

from __future__ import annotations

import time

import pytest

from warm_logic_core.performance.benchmark import (
    BenchmarkStatus,
    BenchmarkResult,
    Benchmark,
    BenchmarkSuite,
    run_benchmark,
)


class TestBenchmarkStatus:
    """Tests for BenchmarkStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert BenchmarkStatus.PENDING.value == "pending"
        assert BenchmarkStatus.RUNNING.value == "running"
        assert BenchmarkStatus.COMPLETED.value == "completed"
        assert BenchmarkStatus.FAILED.value == "failed"
        assert BenchmarkStatus.SKIPPED.value == "skipped"


class TestBenchmarkResult:
    """Tests for BenchmarkResult."""

    def test_result_creation(self):
        """Test result creation."""
        result = BenchmarkResult.create("test_bench")

        assert result.result_id.startswith("BENCH-")
        assert result.benchmark_name == "test_bench"
        assert result.status == BenchmarkStatus.PENDING

    def test_result_to_dict(self):
        """Test result serialization."""
        result = BenchmarkResult.create("test")
        result.iterations = 100
        result.mean_time_ms = 10.5
        result.status = BenchmarkStatus.COMPLETED

        data = result.to_dict()

        assert data["schema_version"] == "benchmark_result_v1"
        assert data["benchmark_name"] == "test"
        assert data["iterations"] == 100
        assert data["mean_time_ms"] == 10.5
        assert data["status"] == "completed"

    def test_result_with_error(self):
        """Test result with error."""
        result = BenchmarkResult.create("test")
        result.status = BenchmarkStatus.FAILED
        result.error = "Test error"

        data = result.to_dict()

        assert data["error"] == "Test error"


class TestBenchmark:
    """Tests for Benchmark."""

    def test_benchmark_creation(self):
        """Test benchmark creation."""

        def test_func():
            return 42

        bench = Benchmark.create(
            name="test",
            func=test_func,
            description="Test benchmark",
        )

        assert bench.name == "test"
        assert bench.description == "Test benchmark"
        assert bench.iterations == 100
        assert bench.enabled is True

    def test_benchmark_run(self):
        """Test running benchmark."""
        counter = {"value": 0}

        def test_func():
            counter["value"] += 1

        bench = Benchmark.create(
            name="test",
            func=test_func,
            iterations=10,
            warmup_iterations=5,
        )

        result = bench.run()

        assert result.status == BenchmarkStatus.COMPLETED
        assert result.iterations == 10
        # Warmup + iterations
        assert counter["value"] == 15
        assert result.mean_time_ms > 0

    def test_benchmark_run_with_setup(self):
        """Test benchmark with setup."""
        state = {"setup_called": False}

        def setup():
            state["setup_called"] = True

        def test_func():
            pass

        bench = Benchmark.create(name="test", func=test_func, iterations=5)
        bench.setup = setup

        bench.run()

        assert state["setup_called"] is True

    def test_benchmark_run_with_teardown(self):
        """Test benchmark with teardown."""
        state = {"teardown_called": False}

        def teardown():
            state["teardown_called"] = True

        def test_func():
            pass

        bench = Benchmark.create(name="test", func=test_func, iterations=5)
        bench.teardown = teardown

        bench.run()

        assert state["teardown_called"] is True

    def test_benchmark_disabled(self):
        """Test disabled benchmark."""
        bench = Benchmark.create(
            name="test",
            func=lambda: None,
        )
        bench.enabled = False

        result = bench.run()

        assert result.status == BenchmarkStatus.SKIPPED

    def test_benchmark_no_function(self):
        """Test benchmark without function."""
        bench = Benchmark(name="test")

        result = bench.run()

        assert result.status == BenchmarkStatus.FAILED
        assert "No function" in result.error

    def test_benchmark_error_handling(self):
        """Test benchmark error handling."""

        def failing_func():
            raise ValueError("Test error")

        bench = Benchmark.create(
            name="test",
            func=failing_func,
            warmup_iterations=0,
            iterations=1,
        )

        result = bench.run()

        assert result.status == BenchmarkStatus.FAILED
        assert "Test error" in result.error

    def test_benchmark_statistics(self):
        """Test benchmark statistics."""

        def test_func():
            time.sleep(0.001)  # 1ms

        bench = Benchmark.create(
            name="test",
            func=test_func,
            iterations=10,
            warmup_iterations=2,
        )

        result = bench.run()

        assert result.mean_time_ms >= 1.0
        assert result.min_time_ms >= 1.0
        assert result.max_time_ms >= result.min_time_ms
        assert result.std_dev_ms >= 0

    def test_benchmark_to_dict(self):
        """Test benchmark serialization."""
        bench = Benchmark.create(
            name="test",
            func=lambda: None,
            description="Test description",
        )

        data = bench.to_dict()

        assert data["name"] == "test"
        assert data["description"] == "Test description"


class TestBenchmarkSuite:
    """Tests for BenchmarkSuite."""

    def test_suite_initialization(self):
        """Test suite initialization."""
        suite = BenchmarkSuite(name="Test Suite")

        assert suite.suite_id.startswith("SUITE-")
        assert suite.name == "Test Suite"
        assert len(suite.list_benchmarks()) == 0

    def test_suite_add_benchmark(self):
        """Test adding benchmark to suite."""
        suite = BenchmarkSuite()
        bench = Benchmark.create("test", lambda: None)

        suite.add_benchmark(bench)

        assert len(suite.list_benchmarks()) == 1
        assert "test" in suite.list_benchmarks()

    def test_suite_remove_benchmark(self):
        """Test removing benchmark from suite."""
        suite = BenchmarkSuite()
        bench = Benchmark.create("test", lambda: None)
        suite.add_benchmark(bench)

        result = suite.remove_benchmark("test")

        assert result is True
        assert len(suite.list_benchmarks()) == 0

    def test_suite_remove_nonexistent(self):
        """Test removing nonexistent benchmark."""
        suite = BenchmarkSuite()

        result = suite.remove_benchmark("nonexistent")

        assert result is False

    def test_suite_get_benchmark(self):
        """Test getting benchmark by name."""
        suite = BenchmarkSuite()
        bench = Benchmark.create("test", lambda: None)
        suite.add_benchmark(bench)

        found = suite.get_benchmark("test")

        assert found is not None
        assert found.name == "test"

    def test_suite_get_nonexistent(self):
        """Test getting nonexistent benchmark."""
        suite = BenchmarkSuite()

        found = suite.get_benchmark("nonexistent")

        assert found is None

    def test_suite_run(self):
        """Test running suite."""
        suite = BenchmarkSuite()
        suite.add_benchmark(Benchmark.create("bench1", lambda: None, iterations=5))
        suite.add_benchmark(Benchmark.create("bench2", lambda: None, iterations=5))

        results = suite.run()

        assert len(results) == 2
        assert all(r.status == BenchmarkStatus.COMPLETED for r in results)

    def test_suite_run_with_filter(self):
        """Test running suite with filter."""
        suite = BenchmarkSuite()
        suite.add_benchmark(Benchmark.create("bench1", lambda: None, iterations=5))
        suite.add_benchmark(Benchmark.create("bench2", lambda: None, iterations=5))

        results = suite.run(filter_names=["bench1"])

        assert len(results) == 1
        assert results[0].benchmark_name == "bench1"

    def test_suite_setup_teardown(self):
        """Test suite setup and teardown."""
        state = {"setup": False, "teardown": False}

        def suite_setup():
            state["setup"] = True

        def suite_teardown():
            state["teardown"] = True

        suite = BenchmarkSuite()
        suite.set_setup(suite_setup)
        suite.set_teardown(suite_teardown)
        suite.add_benchmark(Benchmark.create("test", lambda: None, iterations=5))

        suite.run()

        assert state["setup"] is True
        assert state["teardown"] is True

    def test_suite_get_results(self):
        """Test getting suite results."""
        suite = BenchmarkSuite()
        suite.add_benchmark(Benchmark.create("test", lambda: None, iterations=5))

        suite.run()
        results = suite.get_results()

        assert len(results) == 1

    def test_suite_get_summary(self):
        """Test getting suite summary."""
        suite = BenchmarkSuite(name="Test Suite")
        suite.add_benchmark(Benchmark.create("bench1", lambda: None, iterations=5))

        disabled = Benchmark.create("bench2", lambda: None, iterations=5)
        disabled.enabled = False
        suite.add_benchmark(disabled)

        suite.run()
        summary = suite.get_summary()

        assert summary["name"] == "Test Suite"
        assert summary["total_benchmarks"] == 2
        assert summary["completed"] == 1
        assert summary["skipped"] == 1

    def test_suite_summary_empty(self):
        """Test summary with no results."""
        suite = BenchmarkSuite()
        summary = suite.get_summary()

        assert summary["completed"] == 0

    def test_suite_to_dict(self):
        """Test suite serialization."""
        suite = BenchmarkSuite(name="Test Suite", description="Test desc")
        suite.add_benchmark(Benchmark.create("test", lambda: None))
        suite.run()

        data = suite.to_dict()

        assert data["schema_version"] == "benchmark_suite_v1"
        assert data["name"] == "Test Suite"
        assert len(data["benchmarks"]) == 1
        assert len(data["results"]) == 1


class TestRunBenchmark:
    """Tests for run_benchmark function."""

    def test_run_benchmark_simple(self):
        """Test simple benchmark execution."""
        result = run_benchmark(
            func=lambda: 1 + 1,
            name="simple_add",
            iterations=10,
        )

        assert result.benchmark_name == "simple_add"
        assert result.status == BenchmarkStatus.COMPLETED
        assert result.iterations == 10

    def test_run_benchmark_default_name(self):
        """Test benchmark with default name."""
        result = run_benchmark(lambda: None)

        assert result.benchmark_name == "unnamed"

    def test_run_benchmark_with_timing(self):
        """Test benchmark captures timing."""

        def slow_func():
            time.sleep(0.001)

        result = run_benchmark(
            func=slow_func,
            iterations=5,
            warmup_iterations=1,
        )

        assert result.mean_time_ms >= 1.0


class TestEdgeCases:
    """Edge case tests."""

    def test_zero_iterations(self):
        """Test zero iterations."""
        bench = Benchmark.create(
            name="test",
            func=lambda: None,
            iterations=0,
            warmup_iterations=0,
        )

        result = bench.run()

        # Zero iterations causes statistics.mean([]) to fail
        assert result.status == BenchmarkStatus.FAILED
        assert "mean requires" in result.error or "no" in result.error.lower()

    def test_single_iteration_no_std_dev(self):
        """Test single iteration has no std dev."""
        bench = Benchmark.create(
            name="test",
            func=lambda: None,
            iterations=1,
            warmup_iterations=0,
        )

        result = bench.run()

        assert result.std_dev_ms == 0.0
