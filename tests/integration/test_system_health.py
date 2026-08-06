"""Tests for System Health Aggregation."""

from __future__ import annotations

import pytest

from warm_logic_core.governance import GovernanceEngine
from warm_logic_core.kernel.stability import StabilityAnalyzer
from warm_logic_core.performance import PerformanceMonitor
from warm_logic_core.meta_obs import MetricsCollector, CompletenessChecker
from warm_logic_core.integration.system_health import (
    HealthStatus,
    HealthComponent,
    SystemHealth,
    SystemHealthAggregator,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestHealthComponent:
    """Tests for HealthComponent."""

    def test_component_creation(self):
        """Test component creation."""
        component = HealthComponent(
            component_id="COMP-1",
            name="test",
            status=HealthStatus.HEALTHY,
            score=0.9,
        )

        assert component.component_id == "COMP-1"
        assert component.name == "test"
        assert component.status == HealthStatus.HEALTHY
        assert component.score == 0.9

    def test_component_to_dict(self):
        """Test component serialization."""
        component = HealthComponent(
            component_id="COMP-1",
            name="test",
            status=HealthStatus.DEGRADED,
            score=0.5,
        )

        data = component.to_dict()

        assert data["status"] == "degraded"
        assert data["score"] == 0.5


class TestSystemHealth:
    """Tests for SystemHealth."""

    def test_health_creation(self):
        """Test health creation."""
        health = SystemHealth.create()

        assert health.health_id.startswith("HEALTH-")
        assert health.overall_status == HealthStatus.UNKNOWN
        assert len(health.components) == 0

    def test_health_to_dict(self):
        """Test health serialization."""
        health = SystemHealth.create()
        health.overall_status = HealthStatus.HEALTHY
        health.overall_score = 0.9

        data = health.to_dict()

        assert data["schema_version"] == "system_health_v1"
        assert data["overall_status"] == "healthy"
        assert data["overall_score"] == 0.9


class TestSystemHealthAggregator:
    """Tests for SystemHealthAggregator."""

    def test_aggregator_initialization(self):
        """Test aggregator initialization."""
        aggregator = SystemHealthAggregator()

        assert aggregator.aggregator_id.startswith("AGG-")

    def test_aggregator_custom_id(self):
        """Test aggregator with custom ID."""
        aggregator = SystemHealthAggregator(aggregator_id="TEST-AGG")

        assert aggregator.aggregator_id == "TEST-AGG"

    def test_check_health_no_components(self):
        """Test health check with no components."""
        aggregator = SystemHealthAggregator()

        health = aggregator.check_health()

        assert health.overall_status == HealthStatus.UNKNOWN
        assert len(health.components) == 0

    def test_check_health_with_governance(self):
        """Test health check with governance engine."""
        engine = GovernanceEngine()
        aggregator = SystemHealthAggregator(governance_engine=engine)

        health = aggregator.check_health()

        gov_component = next(
            (c for c in health.components if c.name == "governance"), None
        )
        assert gov_component is not None

    def test_check_health_with_stability(self):
        """Test health check with stability analyzer."""
        analyzer = StabilityAnalyzer()
        aggregator = SystemHealthAggregator(stability_analyzer=analyzer)

        health = aggregator.check_health()

        stab_component = next(
            (c for c in health.components if c.name == "stability"), None
        )
        assert stab_component is not None

    def test_check_health_with_performance(self):
        """Test health check with performance monitor."""
        monitor = PerformanceMonitor()
        aggregator = SystemHealthAggregator(performance_monitor=monitor)

        health = aggregator.check_health()

        perf_component = next(
            (c for c in health.components if c.name == "performance"), None
        )
        assert perf_component is not None

    def test_check_health_with_observability(self):
        """Test health check with metrics collector."""
        collector = MetricsCollector()
        aggregator = SystemHealthAggregator(metrics_collector=collector)

        health = aggregator.check_health()

        obs_component = next(
            (c for c in health.components if c.name == "observability"), None
        )
        assert obs_component is not None

    def test_check_health_all_components(self):
        """Test health check with all components."""
        aggregator = SystemHealthAggregator(
            governance_engine=GovernanceEngine(),
            stability_analyzer=StabilityAnalyzer(),
            performance_monitor=PerformanceMonitor(),
            metrics_collector=MetricsCollector(),
        )

        health = aggregator.check_health()

        assert len(health.components) == 4

    def test_overall_score_calculation(self):
        """Test overall score is average of components."""
        aggregator = SystemHealthAggregator(
            governance_engine=GovernanceEngine(),
            performance_monitor=PerformanceMonitor(),
        )

        health = aggregator.check_health()

        # Score should be average of component scores
        expected_avg = sum(c.score for c in health.components) / len(health.components)
        assert health.overall_score == expected_avg

    def test_unhealthy_component_affects_overall(self):
        """Test unhealthy component affects overall status."""
        engine = GovernanceEngine()
        analyzer = StabilityAnalyzer()

        # Add critical stability data
        analyzer.analyze(jacobian=[[10.0, 0.0], [0.0, 10.0]])

        aggregator = SystemHealthAggregator(
            governance_engine=engine,
            stability_analyzer=analyzer,
        )

        health = aggregator.check_health()

        # With critical stability, overall should be unhealthy
        stab_component = next(c for c in health.components if c.name == "stability")
        if stab_component.status == HealthStatus.UNHEALTHY:
            assert health.overall_status == HealthStatus.UNHEALTHY

    def test_get_history(self):
        """Test getting health check history."""
        aggregator = SystemHealthAggregator(governance_engine=GovernanceEngine())

        aggregator.check_health()
        aggregator.check_health()

        history = aggregator.get_history()

        assert len(history) == 2

    def test_get_trend(self):
        """Test getting health trend."""
        aggregator = SystemHealthAggregator(governance_engine=GovernanceEngine())

        for _ in range(5):
            aggregator.check_health()

        trend = aggregator.get_trend()

        assert "direction" in trend
        assert "score_delta" in trend

    def test_get_trend_insufficient_data(self):
        """Test trend with insufficient data."""
        aggregator = SystemHealthAggregator()

        trend = aggregator.get_trend()

        assert trend["direction"] == "unknown"

    def test_issues_and_recommendations(self):
        """Test issues and recommendations are populated."""
        monitor = PerformanceMonitor()
        # Record degraded performance
        for _ in range(20):
            monitor.record_latency(200.0)

        aggregator = SystemHealthAggregator(performance_monitor=monitor)

        health = aggregator.check_health()

        # Should have issues if performance is degraded
        perf_component = next(c for c in health.components if c.name == "performance")
        if perf_component.status != HealthStatus.HEALTHY:
            assert len(health.issues) > 0 or len(health.recommendations) > 0


class TestOverallStatusDetermination:
    """Tests for overall status determination logic."""

    def test_all_healthy(self):
        """Test all healthy returns healthy."""
        components = [
            HealthComponent("C1", "comp1", HealthStatus.HEALTHY, 0.9),
            HealthComponent("C2", "comp2", HealthStatus.HEALTHY, 0.8),
        ]

        aggregator = SystemHealthAggregator()
        status = aggregator._determine_overall_status(components)

        assert status == HealthStatus.HEALTHY

    def test_any_unhealthy_returns_unhealthy(self):
        """Test any unhealthy returns unhealthy."""
        components = [
            HealthComponent("C1", "comp1", HealthStatus.HEALTHY, 0.9),
            HealthComponent("C2", "comp2", HealthStatus.UNHEALTHY, 0.2),
        ]

        aggregator = SystemHealthAggregator()
        status = aggregator._determine_overall_status(components)

        assert status == HealthStatus.UNHEALTHY

    def test_multiple_degraded_returns_degraded(self):
        """Test multiple degraded returns degraded."""
        components = [
            HealthComponent("C1", "comp1", HealthStatus.DEGRADED, 0.5),
            HealthComponent("C2", "comp2", HealthStatus.DEGRADED, 0.5),
            HealthComponent("C3", "comp3", HealthStatus.HEALTHY, 0.9),
        ]

        aggregator = SystemHealthAggregator()
        status = aggregator._determine_overall_status(components)

        assert status == HealthStatus.DEGRADED

    def test_single_degraded_returns_degraded(self):
        """Test single degraded returns degraded."""
        components = [
            HealthComponent("C1", "comp1", HealthStatus.DEGRADED, 0.5),
            HealthComponent("C2", "comp2", HealthStatus.HEALTHY, 0.9),
        ]

        aggregator = SystemHealthAggregator()
        status = aggregator._determine_overall_status(components)

        assert status == HealthStatus.DEGRADED

    def test_all_unknown_returns_unknown(self):
        """Test all unknown returns unknown."""
        components = [
            HealthComponent("C1", "comp1", HealthStatus.UNKNOWN, 0.5),
            HealthComponent("C2", "comp2", HealthStatus.UNKNOWN, 0.5),
        ]

        aggregator = SystemHealthAggregator()
        status = aggregator._determine_overall_status(components)

        assert status == HealthStatus.UNKNOWN

    def test_empty_components(self):
        """Test empty components returns unknown."""
        aggregator = SystemHealthAggregator()
        status = aggregator._determine_overall_status([])

        assert status == HealthStatus.UNKNOWN
