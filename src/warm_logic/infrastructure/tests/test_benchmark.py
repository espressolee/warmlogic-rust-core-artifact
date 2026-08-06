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
"""Tests for benchmark infrastructure."""

import unittest
from datetime import datetime

from warm_logic.infrastructure.benchmark import (
    BenchmarkConfig,
    BenchmarkReportGenerator,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkStatus,
    BenchmarkSuite,
    CustomTransactionGenerator,
    LatencyMetrics,
    LoadGenerator,
    LoadPattern,
    PerformanceThreshold,
    RegressionDetector,
    SimpleTransactionGenerator,
    ThresholdValidator,
    ThroughputMetrics,
    TransactionResult,
)


class TestLatencyMetrics(unittest.TestCase):
    """Tests for LatencyMetrics."""

    def test_from_samples_empty(self):
        """Test with empty samples."""
        metrics = LatencyMetrics.from_samples([])
        self.assertEqual(metrics.sample_count, 0)
        self.assertEqual(metrics.min_ms, 0.0)

    def test_from_samples_single(self):
        """Test with single sample."""
        metrics = LatencyMetrics.from_samples([10.0])
        self.assertEqual(metrics.sample_count, 1)
        self.assertEqual(metrics.min_ms, 10.0)
        self.assertEqual(metrics.max_ms, 10.0)
        self.assertEqual(metrics.mean_ms, 10.0)

    def test_from_samples_multiple(self):
        """Test with multiple samples."""
        samples = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        metrics = LatencyMetrics.from_samples(samples)

        self.assertEqual(metrics.sample_count, 10)
        self.assertEqual(metrics.min_ms, 1.0)
        self.assertEqual(metrics.max_ms, 10.0)
        self.assertEqual(metrics.mean_ms, 5.5)
        self.assertGreater(metrics.std_dev_ms, 0)

    def test_percentiles(self):
        """Test percentile calculations."""
        samples = list(range(1, 101))  # 1 to 100
        metrics = LatencyMetrics.from_samples([float(x) for x in samples])

        self.assertAlmostEqual(metrics.p50_ms, 50.5, delta=1)
        self.assertAlmostEqual(metrics.p90_ms, 90.1, delta=1)
        self.assertAlmostEqual(metrics.p95_ms, 95.05, delta=1)
        self.assertAlmostEqual(metrics.p99_ms, 99.01, delta=1)


class TestTransactionResult(unittest.TestCase):
    """Tests for TransactionResult."""

    def test_default_values(self):
        """Test default values."""
        result = TransactionResult()
        self.assertEqual(result.tx_id, "")
        self.assertTrue(result.success)
        self.assertEqual(result.latency_ms, 0.0)

    def test_custom_values(self):
        """Test custom values."""
        result = TransactionResult(
            tx_id="tx-123",
            success=False,
            latency_ms=15.5,
            error_message="Test error",
        )
        self.assertEqual(result.tx_id, "tx-123")
        self.assertFalse(result.success)
        self.assertEqual(result.latency_ms, 15.5)
        self.assertEqual(result.error_message, "Test error")


class TestSimpleTransactionGenerator(unittest.TestCase):
    """Tests for SimpleTransactionGenerator."""

    def test_generate_transaction(self):
        """Test generating a transaction."""
        generator = SimpleTransactionGenerator(
            min_latency_ms=1.0,
            max_latency_ms=5.0,
            failure_rate=0.0,
        )
        tx_func = generator.generate()
        result = tx_func()

        self.assertIsNotNone(result.tx_id)
        self.assertTrue(result.success)
        self.assertGreater(result.latency_ms, 0)

    def test_generator_name(self):
        """Test generator name."""
        generator = SimpleTransactionGenerator()
        self.assertEqual(generator.name(), "simple")

    def test_failure_rate(self):
        """Test failure rate behavior."""
        generator = SimpleTransactionGenerator(
            min_latency_ms=0.1,
            max_latency_ms=0.2,
            failure_rate=1.0,  # Always fail
        )
        tx_func = generator.generate()
        result = tx_func()

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Simulated failure")


class TestCustomTransactionGenerator(unittest.TestCase):
    """Tests for CustomTransactionGenerator."""

    def test_custom_function(self):
        """Test with custom transaction function."""

        def custom_tx() -> tuple[bool, str]:
            return True, "Success"

        generator = CustomTransactionGenerator(custom_tx, "custom-test")
        self.assertEqual(generator.name(), "custom-test")

        tx_func = generator.generate()
        result = tx_func()

        self.assertTrue(result.success)
        self.assertEqual(result.error_message, "")

    def test_custom_function_failure(self):
        """Test custom function returning failure."""

        def failing_tx() -> tuple[bool, str]:
            return False, "Custom failure"

        generator = CustomTransactionGenerator(failing_tx)
        tx_func = generator.generate()
        result = tx_func()

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Custom failure")

    def test_custom_function_exception(self):
        """Test custom function that raises exception."""

        def exception_tx() -> tuple[bool, str]:
            raise RuntimeError("Test exception")

        generator = CustomTransactionGenerator(exception_tx)
        tx_func = generator.generate()
        result = tx_func()

        self.assertFalse(result.success)
        self.assertIn("Test exception", result.error_message)


class TestBenchmarkConfig(unittest.TestCase):
    """Tests for BenchmarkConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = BenchmarkConfig()

        self.assertEqual(config.name, "default")
        self.assertEqual(config.target_tps, 1000)
        self.assertEqual(config.duration_seconds, 60)
        self.assertEqual(config.warmup_seconds, 10)
        self.assertEqual(config.num_threads, 10)
        self.assertEqual(config.load_pattern, LoadPattern.CONSTANT)

    def test_custom_config(self):
        """Test custom configuration."""
        config = BenchmarkConfig(
            name="custom",
            target_tps=5000,
            duration_seconds=120,
            load_pattern=LoadPattern.RAMP,
        )

        self.assertEqual(config.name, "custom")
        self.assertEqual(config.target_tps, 5000)
        self.assertEqual(config.duration_seconds, 120)
        self.assertEqual(config.load_pattern, LoadPattern.RAMP)


class TestLoadGenerator(unittest.TestCase):
    """Tests for LoadGenerator."""

    def setUp(self):
        self.config = BenchmarkConfig(
            name="test",
            target_tps=100,
            duration_seconds=2,
            warmup_seconds=0,
            cooldown_seconds=0,
            num_threads=4,
        )
        self.generator = SimpleTransactionGenerator(
            min_latency_ms=0.1,
            max_latency_ms=0.5,
        )

    def test_run_generates_results(self):
        """Test that running generates results."""
        load_gen = LoadGenerator(self.config, self.generator)
        results = load_gen.run()

        self.assertGreater(len(results), 0)
        self.assertIsInstance(results[0], TransactionResult)

    def test_timeline_data(self):
        """Test that timeline data is collected."""
        self.config.measure_interval_seconds = 0.5
        load_gen = LoadGenerator(self.config, self.generator)
        load_gen.run()
        timeline = load_gen.get_timeline()

        self.assertIsInstance(timeline, list)
        if timeline:
            self.assertIn("tps", timeline[0])
            self.assertIn("timestamp", timeline[0])

    def test_stop(self):
        """Test stopping the generator."""
        load_gen = LoadGenerator(self.config, self.generator)
        load_gen.stop()
        # Should not hang or error

    def test_constant_load_pattern(self):
        """Test constant load pattern."""
        self.config.load_pattern = LoadPattern.CONSTANT
        load_gen = LoadGenerator(self.config, self.generator)

        rate = load_gen._get_target_rate(1.0)
        self.assertEqual(rate, float(self.config.target_tps))

    def test_ramp_load_pattern(self):
        """Test ramp load pattern."""
        self.config.load_pattern = LoadPattern.RAMP
        self.config.warmup_seconds = 10
        load_gen = LoadGenerator(self.config, self.generator)

        # At start, should be low
        rate_start = load_gen._get_target_rate(0.0)
        self.assertEqual(rate_start, 0.0)

        # At half warmup, should be half
        rate_mid = load_gen._get_target_rate(5.0)
        self.assertAlmostEqual(rate_mid, float(self.config.target_tps) * 0.5)

        # After warmup, should be full
        rate_full = load_gen._get_target_rate(15.0)
        self.assertEqual(rate_full, float(self.config.target_tps))


class TestBenchmarkRunner(unittest.TestCase):
    """Tests for BenchmarkRunner."""

    def setUp(self):
        self.config = BenchmarkConfig(
            name="test-runner",
            target_tps=50,
            duration_seconds=1,
            warmup_seconds=0,
            cooldown_seconds=0,
            num_threads=2,
        )
        self.generator = SimpleTransactionGenerator(
            min_latency_ms=0.1,
            max_latency_ms=0.5,
            failure_rate=0.0,
        )

    def test_run_completes(self):
        """Test that run completes successfully."""
        runner = BenchmarkRunner(self.config)
        result = runner.run(self.generator)

        self.assertEqual(result.status, BenchmarkStatus.COMPLETED)
        self.assertIsNotNone(result.started_at)
        self.assertIsNotNone(result.completed_at)

    def test_throughput_metrics(self):
        """Test throughput metrics are calculated."""
        runner = BenchmarkRunner(self.config)
        result = runner.run(self.generator)

        self.assertGreater(result.throughput.total_transactions, 0)
        self.assertGreater(result.throughput.tps, 0)
        self.assertGreaterEqual(result.throughput.success_rate, 0)

    def test_latency_metrics(self):
        """Test latency metrics are calculated."""
        runner = BenchmarkRunner(self.config)
        result = runner.run(self.generator)

        self.assertGreater(result.latency.sample_count, 0)
        self.assertGreater(result.latency.mean_ms, 0)
        self.assertGreater(result.latency.p99_ms, 0)

    def test_threshold_pass(self):
        """Test threshold validation when passing."""
        runner = BenchmarkRunner(self.config)
        result = runner.run(self.generator, threshold_tps=1.0)

        self.assertTrue(result.passed_threshold)
        self.assertEqual(result.failure_reason, "")

    def test_threshold_fail(self):
        """Test threshold validation when failing."""
        runner = BenchmarkRunner(self.config)
        result = runner.run(self.generator, threshold_tps=1000000.0)

        self.assertFalse(result.passed_threshold)
        self.assertIn("below threshold", result.failure_reason)

    def test_cancel(self):
        """Test cancelling a benchmark."""
        runner = BenchmarkRunner(self.config)
        runner.cancel()
        # Should not error


class TestBenchmarkSuite(unittest.TestCase):
    """Tests for BenchmarkSuite."""

    def setUp(self):
        self.suite = BenchmarkSuite(name="test-suite")
        self.generator = SimpleTransactionGenerator(
            min_latency_ms=0.1,
            max_latency_ms=0.5,
        )

    def test_add_benchmark(self):
        """Test adding benchmarks."""
        config = BenchmarkConfig(name="test-1", duration_seconds=1)
        self.suite.add_benchmark("test-1", config)

        self.assertEqual(len(self.suite.benchmarks), 1)
        self.assertIn("test-1", self.suite.benchmarks)

    def test_add_benchmark_with_threshold(self):
        """Test adding benchmark with threshold."""
        config = BenchmarkConfig(name="test-2", duration_seconds=1)
        self.suite.add_benchmark("test-2", config, threshold_tps=100.0)

        self.assertEqual(self.suite._thresholds["test-2"], 100.0)

    def test_run_all(self):
        """Test running all benchmarks."""
        config1 = BenchmarkConfig(
            name="test-1",
            duration_seconds=1,
            warmup_seconds=0,
            cooldown_seconds=0,
            target_tps=10,
        )
        config2 = BenchmarkConfig(
            name="test-2",
            duration_seconds=1,
            warmup_seconds=0,
            cooldown_seconds=0,
            target_tps=10,
        )
        self.suite.add_benchmark("test-1", config1)
        self.suite.add_benchmark("test-2", config2)

        results = self.suite.run_all(self.generator)

        self.assertEqual(len(results), 2)
        self.assertIn("test-1", results)
        self.assertIn("test-2", results)

    def test_get_summary_empty(self):
        """Test summary with no results."""
        summary = self.suite.get_summary()

        self.assertEqual(summary["suite"], "test-suite")
        self.assertEqual(summary["benchmarks"], 0)

    def test_get_summary(self):
        """Test summary with results."""
        config = BenchmarkConfig(
            name="test-1",
            duration_seconds=1,
            warmup_seconds=0,
            cooldown_seconds=0,
            target_tps=10,
        )
        self.suite.add_benchmark("test-1", config)
        self.suite.run_all(self.generator)

        summary = self.suite.get_summary()

        self.assertEqual(summary["suite"], "test-suite")
        self.assertEqual(summary["benchmarks"], 1)
        self.assertEqual(len(summary["results"]), 1)


class TestThresholdValidator(unittest.TestCase):
    """Tests for ThresholdValidator."""

    def test_validate_pass(self):
        """Test validation that passes."""
        threshold = PerformanceThreshold(
            min_tps=10.0,
            max_p99_ms=100.0,
            max_p95_ms=50.0,
            min_success_rate=0.9,
            max_error_rate=0.1,  # Allow up to 10% error rate
        )
        validator = ThresholdValidator(threshold)

        result = BenchmarkResult()
        result.throughput = ThroughputMetrics(tps=100.0, success_rate=0.99)
        result.latency = LatencyMetrics(p99_ms=50.0, p95_ms=30.0)

        passed, violations = validator.validate(result)

        self.assertTrue(passed)
        self.assertEqual(len(violations), 0)

    def test_validate_fail_tps(self):
        """Test validation that fails on TPS."""
        threshold = PerformanceThreshold(min_tps=1000.0)
        validator = ThresholdValidator(threshold)

        result = BenchmarkResult()
        result.throughput = ThroughputMetrics(tps=500.0, success_rate=0.999)
        result.latency = LatencyMetrics(p99_ms=10.0, p95_ms=5.0)

        passed, violations = validator.validate(result)

        self.assertFalse(passed)
        self.assertIn("TPS", violations[0])

    def test_validate_fail_latency(self):
        """Test validation that fails on latency."""
        threshold = PerformanceThreshold(max_p99_ms=10.0)
        validator = ThresholdValidator(threshold)

        result = BenchmarkResult()
        result.throughput = ThroughputMetrics(tps=2000.0, success_rate=0.999)
        result.latency = LatencyMetrics(p99_ms=50.0, p95_ms=5.0)

        passed, violations = validator.validate(result)

        self.assertFalse(passed)
        self.assertIn("P99 latency", violations[0])

    def test_validate_fail_success_rate(self):
        """Test validation that fails on success rate."""
        threshold = PerformanceThreshold(min_success_rate=0.999)
        validator = ThresholdValidator(threshold)

        result = BenchmarkResult()
        result.throughput = ThroughputMetrics(tps=2000.0, success_rate=0.9)
        result.latency = LatencyMetrics(p99_ms=10.0, p95_ms=5.0)

        passed, violations = validator.validate(result)

        self.assertFalse(passed)
        self.assertIn("Success rate", violations[0])


class TestRegressionDetector(unittest.TestCase):
    """Tests for RegressionDetector."""

    def setUp(self):
        self.detector = RegressionDetector(tolerance_percent=10.0)

    def test_set_baseline(self):
        """Test setting baseline."""
        baseline = self.detector.set_baseline(
            name="test",
            tps=1000.0,
            p99_ms=50.0,
            p95_ms=30.0,
        )

        self.assertEqual(baseline.name, "test")
        self.assertEqual(baseline.tps, 1000.0)
        self.assertIn("test", self.detector.baselines)

    def test_no_regression(self):
        """Test when no regression detected."""
        self.detector.set_baseline("test", tps=1000.0, p99_ms=50.0, p95_ms=30.0)

        result = BenchmarkResult()
        result.throughput = ThroughputMetrics(tps=1000.0)
        result.latency = LatencyMetrics(p99_ms=50.0, p95_ms=30.0)

        has_regression, regressions = self.detector.check_regression("test", result)

        self.assertFalse(has_regression)
        self.assertEqual(len(regressions), 0)

    def test_tps_regression(self):
        """Test TPS regression detection."""
        self.detector.set_baseline("test", tps=1000.0, p99_ms=50.0, p95_ms=30.0)

        result = BenchmarkResult()
        result.throughput = ThroughputMetrics(tps=800.0)  # 20% regression
        result.latency = LatencyMetrics(p99_ms=50.0, p95_ms=30.0)

        has_regression, regressions = self.detector.check_regression("test", result)

        self.assertTrue(has_regression)
        self.assertIn("TPS regression", regressions[0])

    def test_latency_regression(self):
        """Test latency regression detection."""
        self.detector.set_baseline("test", tps=1000.0, p99_ms=50.0, p95_ms=30.0)

        result = BenchmarkResult()
        result.throughput = ThroughputMetrics(tps=1000.0)
        result.latency = LatencyMetrics(p99_ms=70.0, p95_ms=30.0)  # 40% regression

        has_regression, regressions = self.detector.check_regression("test", result)

        self.assertTrue(has_regression)
        self.assertIn("P99 regression", regressions[0])

    def test_no_baseline(self):
        """Test with no baseline set."""
        result = BenchmarkResult()
        has_regression, regressions = self.detector.check_regression(
            "nonexistent", result
        )

        self.assertFalse(has_regression)
        self.assertEqual(len(regressions), 0)


class TestBenchmarkReportGenerator(unittest.TestCase):
    """Tests for BenchmarkReportGenerator."""

    def setUp(self):
        self.generator = BenchmarkReportGenerator()
        self.result = BenchmarkResult(
            config=BenchmarkConfig(name="test-report"),
            status=BenchmarkStatus.COMPLETED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        self.result.throughput = ThroughputMetrics(
            total_transactions=1000,
            successful_transactions=990,
            failed_transactions=10,
            duration_seconds=10.0,
            tps=100.0,
            success_rate=0.99,
            peak_tps=120.0,
            sustained_tps=95.0,
        )
        self.result.latency = LatencyMetrics(
            min_ms=1.0,
            max_ms=100.0,
            mean_ms=10.0,
            median_ms=9.0,
            p50_ms=9.0,
            p90_ms=20.0,
            p95_ms=30.0,
            p99_ms=50.0,
            p999_ms=80.0,
            std_dev_ms=5.0,
            sample_count=990,
        )

    def test_generate_text_report(self):
        """Test text report generation."""
        report = self.generator.generate_text_report(self.result)

        self.assertIn("Benchmark Report", report)
        self.assertIn("test-report", report)
        self.assertIn("TPS: 100.0", report)
        self.assertIn("P99: 50.0", report)
        self.assertIn("Success Rate: 99.00%", report)

    def test_generate_json_report(self):
        """Test JSON report generation."""
        report = self.generator.generate_json_report(self.result)

        self.assertIsInstance(report, dict)
        self.assertEqual(report["config"]["name"], "test-report")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["throughput"]["tps"], 100.0)
        self.assertEqual(report["latency"]["p99_ms"], 50.0)

    def test_text_report_with_errors(self):
        """Test text report with error summary."""
        self.result.error_summary = {"Connection timeout": 5, "Invalid response": 5}
        report = self.generator.generate_text_report(self.result)

        self.assertIn("Error Summary", report)
        self.assertIn("Connection timeout", report)

    def test_text_report_with_failure(self):
        """Test text report with failure reason."""
        self.result.failure_reason = "TPS below threshold"
        report = self.generator.generate_text_report(self.result)

        self.assertIn("Failure Reason", report)
        self.assertIn("TPS below threshold", report)


class TestPerformanceThreshold(unittest.TestCase):
    """Tests for PerformanceThreshold."""

    def test_default_values(self):
        """Test default threshold values."""
        threshold = PerformanceThreshold()

        self.assertEqual(threshold.min_tps, 1000.0)
        self.assertEqual(threshold.max_p99_ms, 100.0)
        self.assertEqual(threshold.max_p95_ms, 50.0)
        self.assertEqual(threshold.min_success_rate, 0.999)
        self.assertEqual(threshold.max_error_rate, 0.001)

    def test_custom_values(self):
        """Test custom threshold values."""
        threshold = PerformanceThreshold(
            min_tps=5000.0,
            max_p99_ms=50.0,
            min_success_rate=0.9999,
        )

        self.assertEqual(threshold.min_tps, 5000.0)
        self.assertEqual(threshold.max_p99_ms, 50.0)
        self.assertEqual(threshold.min_success_rate, 0.9999)


if __name__ == "__main__":
    unittest.main()
