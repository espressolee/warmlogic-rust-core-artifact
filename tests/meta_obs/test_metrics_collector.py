"""Tests for MetricsCollector."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from warm_logic_core.meta_obs.metrics_collector import (
    AggregationSpec,
    HistogramData,
    MetricCategory,
    MetricContext,
    MetricEntry,
    MetricsCollector,
    MetricStatus,
    MetricThresholds,
    MetricType,
)


class TestMetricThresholds:
    """Tests for MetricThresholds."""

    def test_thresholds_creation(self):
        """Test threshold creation."""
        thresholds = MetricThresholds(warning=80, critical=95, target=50)

        assert thresholds.warning == 80
        assert thresholds.critical == 95
        assert thresholds.target == 50

    def test_thresholds_to_dict(self):
        """Test threshold serialization."""
        thresholds = MetricThresholds(warning=100)

        data = thresholds.to_dict()

        assert data["warning"] == 100
        assert "critical" not in data  # None values excluded


class TestMetricContext:
    """Tests for MetricContext."""

    def test_context_creation(self):
        """Test context creation."""
        context = MetricContext(
            experiment_id="EXP-001",
            run_id="RUN-001",
            component="governance",
            environment="staging",
        )

        assert context.experiment_id == "EXP-001"
        assert context.environment == "staging"

    def test_context_to_dict(self):
        """Test context serialization."""
        context = MetricContext(experiment_id="EXP-001")

        data = context.to_dict()

        assert data["experiment_id"] == "EXP-001"
        assert "run_id" not in data  # Empty values excluded


class TestMetricEntry:
    """Tests for MetricEntry."""

    def test_entry_creation(self):
        """Test entry creation."""
        entry = MetricEntry(
            metric_id="METRIC-001",
            metric_name="latency_p99",
            metric_type=MetricType.HISTOGRAM,
            value=95.5,
            unit="ms",
            category=MetricCategory.LATENCY,
        )

        assert entry.metric_id == "METRIC-001"
        assert entry.metric_name == "latency_p99"
        assert entry.value == 95.5
        assert entry.unit == "ms"

    def test_entry_to_dict(self):
        """Test entry serialization."""
        entry = MetricEntry(
            metric_id="METRIC-002",
            metric_name="error_count",
            metric_type=MetricType.COUNTER,
            value=5,
            category=MetricCategory.ERROR_RATE,
        )

        data = entry.to_dict()

        assert data["schema_version"] == "meta_obs_metric_v1"
        assert data["metric_id"] == "METRIC-002"
        assert data["metric_type"] == "counter"
        assert data["category"] == "error_rate"


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        context = MetricContext(experiment_id="EXP-001")
        collector = MetricsCollector(context=context)

        assert collector.context.experiment_id == "EXP-001"

    def test_increment_counter(self):
        """Test counter increments."""
        collector = MetricsCollector()

        collector.increment("requests_total")
        collector.increment("requests_total")
        collector.increment("requests_total", value=3)

        assert collector.get_counter("requests_total") == 5

    def test_increment_with_dimensions(self):
        """Test counter with dimensions."""
        collector = MetricsCollector()

        collector.increment("requests", dimensions={"method": "GET"})
        collector.increment("requests", dimensions={"method": "POST"})
        collector.increment("requests", dimensions={"method": "GET"})

        assert collector.get_counter("requests", {"method": "GET"}) == 2
        assert collector.get_counter("requests", {"method": "POST"}) == 1

    def test_gauge(self):
        """Test gauge metrics."""
        collector = MetricsCollector()

        collector.gauge("cpu_usage", 45.5)
        assert collector.get_gauge("cpu_usage") == 45.5

        collector.gauge("cpu_usage", 60.0)
        assert collector.get_gauge("cpu_usage") == 60.0

    def test_histogram(self):
        """Test histogram metrics."""
        collector = MetricsCollector()

        for latency in [10, 20, 30, 40, 50, 100, 200]:
            collector.histogram("latency_ms", latency)

        stats = collector.get_histogram_stats("latency_ms")

        assert stats["count"] == 7
        assert stats["min"] == 10
        assert stats["max"] == 200
        assert stats["avg"] == pytest.approx(64.28, rel=0.01)

    def test_histogram_percentiles(self):
        """Test histogram percentile calculations."""
        collector = MetricsCollector()

        # Add 100 values
        for i in range(100):
            collector.histogram("response_time", i)

        stats = collector.get_histogram_stats("response_time")

        assert stats["p50"] == pytest.approx(49, abs=1)
        assert stats["p90"] == pytest.approx(89, abs=1)
        assert stats["p99"] == pytest.approx(98, abs=1)

    def test_rate(self):
        """Test rate metrics."""
        collector = MetricsCollector()

        # Record some events
        for _ in range(10):
            collector.rate("events")

        rate = collector.get_rate("events", window_seconds=60.0)

        assert rate > 0

    def test_record_metric(self):
        """Test recording a full metric."""
        collector = MetricsCollector()

        entry = collector.record(
            name="test_metric",
            value=42.0,
            metric_type=MetricType.GAUGE,
            unit="units",
            category=MetricCategory.CUSTOM,
        )

        assert entry.metric_name == "test_metric"
        assert entry.value == 42.0
        assert entry.metric_id.startswith("METRIC-")

    def test_record_latency(self):
        """Test recording latency metric."""
        collector = MetricsCollector()

        entry = collector.record_latency("api_latency", 150.0)

        assert entry.metric_name == "api_latency"
        assert entry.value == 150.0
        assert entry.unit == "ms"
        assert entry.category == MetricCategory.LATENCY

    def test_record_error(self):
        """Test recording error."""
        collector = MetricsCollector()

        collector.record_error("api_errors")
        collector.record_error("api_errors")
        collector.record_error("api_errors")

        assert collector.get_counter("api_errors") == 3

    def test_get_all_metrics(self):
        """Test getting all metrics."""
        collector = MetricsCollector()

        collector.record("metric1", 10.0)
        collector.record("metric2", 20.0)
        collector.record("metric3", 30.0)

        all_metrics = collector.get_all_metrics()

        assert len(all_metrics) == 3

    def test_clear(self):
        """Test clearing metrics."""
        collector = MetricsCollector()

        collector.increment("counter1")
        collector.gauge("gauge1", 100)
        collector.histogram("hist1", 50)
        collector.record("metric1", 10)

        collector.clear()

        assert collector.get_counter("counter1") == 0
        assert collector.get_gauge("gauge1") is None
        assert collector.get_histogram_stats("hist1") == {}
        assert len(collector.get_all_metrics()) == 0

    def test_aggregate_avg(self):
        """Test average aggregation."""
        collector = MetricsCollector()

        for value in [10, 20, 30, 40, 50]:
            collector.record("test_metric", value)

        agg = collector.aggregate("test_metric", method="avg")

        assert agg is not None
        assert agg.value == pytest.approx(30.0)
        assert agg.metric_type == MetricType.DERIVED

    def test_aggregate_sum(self):
        """Test sum aggregation."""
        collector = MetricsCollector()

        for value in [10, 20, 30]:
            collector.record("values", value)

        agg = collector.aggregate("values", method="sum")

        assert agg is not None
        assert agg.value == 60.0

    def test_aggregate_percentile(self):
        """Test percentile aggregation."""
        collector = MetricsCollector()

        for i in range(100):
            collector.record("latency", i)

        p99 = collector.aggregate("latency", method="p99")

        assert p99 is not None
        assert p99.value >= 98

    def test_threshold_status_evaluation(self):
        """Test threshold-based status evaluation."""
        collector = MetricsCollector(
            default_thresholds={"cpu_usage": MetricThresholds(warning=70, critical=90)}
        )

        normal = collector.record("cpu_usage", 50)
        warning = collector.record("cpu_usage", 80)
        critical = collector.record("cpu_usage", 95)

        assert normal.status == MetricStatus.NORMAL
        assert warning.status == MetricStatus.WARNING
        assert critical.status == MetricStatus.CRITICAL

    def test_export_json(self):
        """Test JSON export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MetricsCollector()

            collector.record("metric1", 10)
            collector.record("metric2", 20)

            path = Path(tmpdir) / "metrics.json"
            collector.export_json(path)

            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert len(data) == 2

    def test_export_jsonl(self):
        """Test JSONL export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MetricsCollector()

            collector.record("metric1", 10)
            collector.record("metric2", 20)
            collector.record("metric3", 30)

            path = Path(tmpdir) / "metrics.jsonl"
            collector.export_jsonl(path)

            assert path.exists()
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 3

    def test_export_prometheus(self):
        """Test Prometheus format export."""
        collector = MetricsCollector()

        collector.increment("requests_total")
        collector.gauge("active_connections", 42)
        collector.histogram("response_time_ms", 150)

        output = collector.export_prometheus()

        assert "requests_total" in output
        assert "active_connections" in output
        assert "42" in output

    def test_dimensions_in_export(self):
        """Test dimensions in Prometheus export."""
        collector = MetricsCollector()

        collector.increment(
            "http_requests", dimensions={"method": "GET", "status": "200"}
        )

        output = collector.export_prometheus()

        assert 'method="GET"' in output
        assert 'status="200"' in output

    def test_start_stop(self):
        """Test start and stop collection loop."""
        collector = MetricsCollector(collection_interval_ms=100)

        collector.start()
        time.sleep(0.2)
        collector.stop()

        # Should not raise any errors

    def test_empty_histogram_stats(self):
        """Test histogram stats when empty."""
        collector = MetricsCollector()

        stats = collector.get_histogram_stats("nonexistent")

        assert stats == {}

    def test_derived_metric_references(self):
        """Test derived metric references source metrics."""
        collector = MetricsCollector()

        for i in range(5):
            collector.record("source_metric", i * 10)

        agg = collector.aggregate("source_metric", method="avg")

        assert agg is not None
        assert len(agg.derived_from) > 0

    def test_context_propagation(self):
        """Test context propagation to metrics."""
        context = MetricContext(
            experiment_id="EXP-TEST",
            run_id="RUN-123",
            environment="prod",
        )
        collector = MetricsCollector(context=context)

        entry = collector.record("test_metric", 100)

        assert entry.context.experiment_id == "EXP-TEST"
        assert entry.context.run_id == "RUN-123"
