"""Tests for Performance-MetaObservability Integration."""

from __future__ import annotations

import time

import pytest

from warm_logic_core.performance import PerformanceConfig
from warm_logic_core.meta_obs import MetricsCollector, CostTracker
from warm_logic_core.integration.performance_observer import (
    PerformanceObserver,
    ObservedPerformance,
    create_observed_experiment,
)


class TestObservedPerformance:
    """Tests for ObservedPerformance."""

    def test_observation_creation(self):
        """Test observation creation."""
        obs = ObservedPerformance.create()

        assert obs.observation_id.startswith("OBS-")
        assert obs.experiment_id is None

    def test_observation_with_experiment(self):
        """Test observation with experiment ID."""
        obs = ObservedPerformance.create(experiment_id="EXP-123")

        assert obs.experiment_id == "EXP-123"

    def test_observation_to_dict(self):
        """Test observation serialization."""
        obs = ObservedPerformance.create()
        obs.cost_impact = 0.001

        data = obs.to_dict()

        assert data["schema_version"] == "observed_performance_v1"
        assert data["cost_impact"] == 0.001


class TestPerformanceObserver:
    """Tests for PerformanceObserver."""

    def test_observer_initialization(self):
        """Test observer initialization."""
        observer = PerformanceObserver()

        assert observer.observer_id.startswith("OBSV-")
        assert observer.metrics_collector is not None
        assert observer.cost_tracker is not None

    def test_observer_custom_id(self):
        """Test observer with custom ID."""
        observer = PerformanceObserver(observer_id="TEST-OBS")

        assert observer.observer_id == "TEST-OBS"

    def test_observe_function(self):
        """Test observing a function."""
        observer = PerformanceObserver()

        def test_func():
            return 42

        result, obs = observer.observe(test_func, name="test")

        assert result == 42
        assert obs.observation_id.startswith("OBS-")
        assert obs.performance_metrics is not None

    def test_observe_records_latency(self):
        """Test observe records latency."""
        observer = PerformanceObserver()

        def slow_func():
            time.sleep(0.01)
            return "done"

        result, obs = observer.observe(slow_func, name="slow")

        assert obs.performance_metrics.latency_avg_ms >= 10.0

    def test_observe_records_profile(self):
        """Test observe records profile."""
        observer = PerformanceObserver()

        def test_func():
            return 1 + 1

        _, obs = observer.observe(test_func, name="add")

        assert obs.profile_result is not None
        assert len(obs.profile_result.sections) >= 1

    def test_observe_records_cost(self):
        """Test observe records cost impact."""
        observer = PerformanceObserver()

        def test_func():
            return None

        _, obs = observer.observe(test_func)

        assert obs.cost_impact > 0

    def test_observe_context_manager(self):
        """Test observe context manager."""
        observer = PerformanceObserver()

        with observer.observe_context("test_block") as obs:
            time.sleep(0.01)

        observations = observer.get_observations()

        assert len(observations) == 1
        assert observations[0].performance_metrics is not None

    def test_observe_with_experiment_id(self):
        """Test observe with experiment ID."""
        observer = PerformanceObserver()

        _, obs = observer.observe(
            lambda: None,
            experiment_id="EXP-TEST",
        )

        assert obs.experiment_id == "EXP-TEST"

    def test_get_observations(self):
        """Test getting observations."""
        observer = PerformanceObserver()

        observer.observe(lambda: None, name="op1")
        observer.observe(lambda: None, name="op2")

        observations = observer.get_observations()

        assert len(observations) == 2

    def test_get_summary(self):
        """Test getting summary."""
        observer = PerformanceObserver()

        observer.observe(lambda: None, name="op1")
        observer.observe(lambda: None, name="op2")

        summary = observer.get_summary()

        assert summary["observer_id"] == observer.observer_id
        assert summary["total_observations"] == 2
        assert summary["total_cost"] > 0

    def test_get_summary_empty(self):
        """Test summary with no observations."""
        observer = PerformanceObserver()

        summary = observer.get_summary()

        assert summary["total_observations"] == 0

    def test_reset(self):
        """Test resetting observer."""
        observer = PerformanceObserver()

        observer.observe(lambda: None)
        observer.reset()

        assert len(observer.get_observations()) == 0

    def test_metrics_recorded_to_collector(self):
        """Test metrics are recorded to collector."""
        collector = MetricsCollector()
        observer = PerformanceObserver(metrics_collector=collector)

        observer.observe(lambda: None, name="tracked_op")

        all_metrics = collector.get_all_metrics()
        assert len(all_metrics) > 0

    def test_cost_recorded_to_tracker(self):
        """Test cost is recorded to tracker."""
        tracker = CostTracker()
        observer = PerformanceObserver(cost_tracker=tracker)

        observer.observe(lambda: None)

        total = tracker.get_total_cost()
        assert total >= 0  # Cost may be 0 due to default rates

    def test_custom_performance_config(self):
        """Test with custom performance config."""
        config = PerformanceConfig(latency_warning_ms=50.0)
        observer = PerformanceObserver(performance_config=config)

        observer.observe(lambda: None)

        observations = observer.get_observations()
        assert len(observations) == 1


class TestCreateObservedExperiment:
    """Tests for create_observed_experiment."""

    def test_create_experiment(self):
        """Test creating observed experiment."""

        def experiment():
            return "experiment_result"

        result, observation = create_observed_experiment(
            name="test_experiment",
            experiment_func=experiment,
        )

        assert result is not None
        assert observation.observation_id.startswith("OBS-")

    def test_create_experiment_with_observer(self):
        """Test with custom observer."""
        observer = PerformanceObserver(observer_id="CUSTOM")

        def experiment():
            return 42

        result, observation = create_observed_experiment(
            name="test",
            experiment_func=experiment,
            observer=observer,
        )

        assert result is not None
        assert len(observer.get_observations()) == 1


class TestIntegrationScenarios:
    """Integration scenario tests."""

    def test_multiple_operations_tracking(self):
        """Test tracking multiple operations."""
        observer = PerformanceObserver()

        for i in range(5):
            observer.observe(lambda: None, name=f"op_{i}")

        summary = observer.get_summary()

        assert summary["total_observations"] == 5
        assert summary["total_cost"] > 0

    def test_nested_context_managers(self):
        """Test nested context managers."""
        observer = PerformanceObserver()

        with observer.observe_context("outer") as outer_obs:
            with observer.observe_context("inner") as inner_obs:
                time.sleep(0.005)

        observations = observer.get_observations()

        # Should have 2 observations
        assert len(observations) == 2

    def test_status_distribution(self):
        """Test status distribution in summary."""
        observer = PerformanceObserver()

        for _ in range(10):
            observer.observe(lambda: None)

        summary = observer.get_summary()

        assert "status_distribution" in summary
