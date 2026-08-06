"""Tests for Performance Monitor."""

from __future__ import annotations

import time

import pytest

from warm_logic_core.performance.monitor import (
    PerformanceStatus,
    PerformanceConfig,
    LatencyBucket,
    ThroughputMetrics,
    PerformanceMetrics,
    PerformanceMonitor,
)


class TestPerformanceStatus:
    """Tests for PerformanceStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert PerformanceStatus.OPTIMAL.value == "optimal"
        assert PerformanceStatus.NORMAL.value == "normal"
        assert PerformanceStatus.DEGRADED.value == "degraded"
        assert PerformanceStatus.CRITICAL.value == "critical"
        assert PerformanceStatus.UNKNOWN.value == "unknown"


class TestPerformanceConfig:
    """Tests for PerformanceConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = PerformanceConfig()

        assert config.latency_warning_ms == 100.0
        assert config.latency_critical_ms == 500.0
        assert config.window_size == 1000
        assert config.bucket_count == 10

    def test_custom_config(self):
        """Test custom configuration."""
        config = PerformanceConfig(
            latency_warning_ms=50.0,
            bucket_count=20,
        )

        assert config.latency_warning_ms == 50.0
        assert config.bucket_count == 20


class TestLatencyBucket:
    """Tests for LatencyBucket."""

    def test_bucket_creation(self):
        """Test bucket creation."""
        bucket = LatencyBucket(lower_ms=0.0, upper_ms=100.0)

        assert bucket.lower_ms == 0.0
        assert bucket.upper_ms == 100.0
        assert bucket.count == 0

    def test_bucket_contains(self):
        """Test bucket contains check."""
        bucket = LatencyBucket(lower_ms=10.0, upper_ms=20.0)

        assert bucket.contains(15.0) is True
        assert bucket.contains(10.0) is True
        assert bucket.contains(20.0) is False
        assert bucket.contains(5.0) is False

    def test_bucket_to_dict(self):
        """Test bucket serialization."""
        bucket = LatencyBucket(lower_ms=0.0, upper_ms=100.0, count=5)
        data = bucket.to_dict()

        assert data["lower_ms"] == 0.0
        assert data["upper_ms"] == 100.0
        assert data["count"] == 5


class TestThroughputMetrics:
    """Tests for ThroughputMetrics."""

    def test_throughput_creation(self):
        """Test throughput metrics creation."""
        throughput = ThroughputMetrics(
            ops_per_second=100.0,
            bytes_per_second=1024.0,
            total_ops=1000,
        )

        assert throughput.ops_per_second == 100.0
        assert throughput.bytes_per_second == 1024.0
        assert throughput.total_ops == 1000

    def test_throughput_to_dict(self):
        """Test throughput serialization."""
        throughput = ThroughputMetrics(ops_per_second=50.0)
        data = throughput.to_dict()

        assert data["ops_per_second"] == 50.0


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics."""

    def test_metrics_creation(self):
        """Test metrics creation."""
        metrics = PerformanceMetrics.create()

        assert metrics.metrics_id.startswith("PERF-")
        assert metrics.status == PerformanceStatus.UNKNOWN
        assert metrics.sample_count == 0

    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        metrics = PerformanceMetrics.create()
        metrics.latency_p95_ms = 50.0
        metrics.sample_count = 100

        data = metrics.to_dict()

        assert data["schema_version"] == "performance_metrics_v1"
        assert data["latency_p95_ms"] == 50.0
        assert data["sample_count"] == 100

    def test_metrics_with_throughput(self):
        """Test metrics with throughput."""
        metrics = PerformanceMetrics.create()
        metrics.throughput = ThroughputMetrics(ops_per_second=100.0)

        data = metrics.to_dict()

        assert data["throughput"]["ops_per_second"] == 100.0


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor."""

    def test_monitor_initialization(self):
        """Test monitor initialization."""
        monitor = PerformanceMonitor()

        assert monitor.monitor_id.startswith("MON-")
        assert monitor.config.window_size == 1000

    def test_monitor_custom_id(self):
        """Test monitor with custom ID."""
        monitor = PerformanceMonitor(monitor_id="TEST-MON")

        assert monitor.monitor_id == "TEST-MON"

    def test_monitor_custom_config(self):
        """Test monitor with custom config."""
        config = PerformanceConfig(latency_warning_ms=50.0)
        monitor = PerformanceMonitor(config=config)

        assert monitor.config.latency_warning_ms == 50.0

    def test_record_latency(self):
        """Test recording latency."""
        monitor = PerformanceMonitor()

        monitor.record_latency(10.0)
        monitor.record_latency(20.0)

        metrics = monitor.get_metrics()
        assert metrics.sample_count == 2

    def test_record_operation(self):
        """Test recording operation with bytes."""
        monitor = PerformanceMonitor()

        monitor.record_operation(10.0, bytes_processed=1024)
        monitor.record_operation(20.0, bytes_processed=2048)

        metrics = monitor.get_metrics()
        assert metrics.sample_count == 2
        assert metrics.throughput is not None
        assert metrics.throughput.total_ops == 2

    def test_time_operation(self):
        """Test timing operation."""
        monitor = PerformanceMonitor()

        def slow_func():
            time.sleep(0.01)
            return 42

        result = monitor.time_operation(slow_func)

        assert result == 42
        metrics = monitor.get_metrics()
        assert metrics.sample_count == 1
        assert metrics.latency_avg_ms >= 10.0

    def test_percentiles(self):
        """Test percentile calculation."""
        monitor = PerformanceMonitor()

        # Add 100 samples from 1 to 100
        for i in range(1, 101):
            monitor.record_latency(float(i))

        metrics = monitor.get_metrics()

        assert metrics.latency_min_ms == 1.0
        assert metrics.latency_max_ms == 100.0
        # p50 is at index 50 (0-indexed) = 51.0
        assert metrics.latency_p50_ms == 51.0

    def test_bucket_histogram(self):
        """Test latency bucket histogram."""
        config = PerformanceConfig(bucket_count=10, bucket_max_ms=100.0)
        monitor = PerformanceMonitor(config=config)

        # Add samples in first bucket (0-10ms)
        for _ in range(5):
            monitor.record_latency(5.0)

        metrics = monitor.get_metrics()

        # First bucket should have 5 samples
        assert metrics.buckets[0].count == 5

    def test_status_optimal(self):
        """Test optimal status."""
        config = PerformanceConfig(
            latency_warning_ms=100.0,
            throughput_warning=1.0,
        )
        monitor = PerformanceMonitor(config=config)

        # Add fast samples
        for _ in range(20):
            monitor.record_latency(10.0)

        metrics = monitor.get_metrics()
        assert metrics.status == PerformanceStatus.OPTIMAL

    def test_status_degraded(self):
        """Test degraded status."""
        config = PerformanceConfig(
            latency_warning_ms=50.0,
            latency_critical_ms=200.0,
        )
        monitor = PerformanceMonitor(config=config)

        # Add samples above warning
        for _ in range(20):
            monitor.record_latency(100.0)

        metrics = monitor.get_metrics()
        assert metrics.status == PerformanceStatus.DEGRADED

    def test_status_critical(self):
        """Test critical status."""
        config = PerformanceConfig(latency_critical_ms=100.0)
        monitor = PerformanceMonitor(config=config)

        # Add samples above critical
        for _ in range(20):
            monitor.record_latency(500.0)

        metrics = monitor.get_metrics()
        assert metrics.status == PerformanceStatus.CRITICAL

    def test_status_unknown_few_samples(self):
        """Test unknown status with few samples."""
        monitor = PerformanceMonitor()

        monitor.record_latency(10.0)

        metrics = monitor.get_metrics()
        assert metrics.status == PerformanceStatus.UNKNOWN

    def test_reset(self):
        """Test resetting monitor."""
        monitor = PerformanceMonitor()

        for _ in range(10):
            monitor.record_latency(10.0)

        monitor.reset()

        metrics = monitor.get_metrics()
        assert metrics.sample_count == 0

    def test_get_summary(self):
        """Test getting summary."""
        monitor = PerformanceMonitor()

        for _ in range(20):
            monitor.record_latency(50.0)

        summary = monitor.get_summary()

        assert "monitor_id" in summary
        assert summary["sample_count"] == 20
        assert summary["latency_avg_ms"] == 50.0

    def test_window_size_limit(self):
        """Test window size limit."""
        config = PerformanceConfig(window_size=10)
        monitor = PerformanceMonitor(config=config)

        # Add more samples than window size
        for i in range(20):
            monitor.record_latency(float(i))

        metrics = monitor.get_metrics()
        assert metrics.sample_count == 10

    def test_throughput_calculation(self):
        """Test throughput calculation."""
        monitor = PerformanceMonitor()

        for _ in range(10):
            monitor.record_latency(10.0)

        metrics = monitor.get_metrics()

        assert metrics.throughput is not None
        assert metrics.throughput.ops_per_second > 0
        assert metrics.throughput.total_ops == 10


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_metrics(self):
        """Test getting metrics with no samples."""
        monitor = PerformanceMonitor()
        metrics = monitor.get_metrics()

        assert metrics.sample_count == 0
        assert metrics.latency_avg_ms == 0.0

    def test_single_sample(self):
        """Test with single sample."""
        monitor = PerformanceMonitor()
        monitor.record_latency(50.0)

        metrics = monitor.get_metrics()

        assert metrics.sample_count == 1
        assert metrics.latency_avg_ms == 50.0
        assert metrics.latency_min_ms == 50.0
        assert metrics.latency_max_ms == 50.0

    def test_overflow_bucket(self):
        """Test overflow bucket for high latencies."""
        config = PerformanceConfig(bucket_max_ms=100.0)
        monitor = PerformanceMonitor(config=config)

        monitor.record_latency(500.0)

        metrics = monitor.get_metrics()
        # Last bucket is overflow
        assert metrics.buckets[-1].count == 1
