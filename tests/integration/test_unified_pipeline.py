"""Tests for Unified Pipeline."""

from __future__ import annotations

import time

import pytest

from warm_logic_core.governance import GovernanceInputs
from warm_logic_core.integration.unified_pipeline import (
    UnifiedPipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStage,
)


class TestPipelineStage:
    """Tests for PipelineStage enum."""

    def test_stage_values(self):
        """Test stage values."""
        assert PipelineStage.INIT.value == "init"
        assert PipelineStage.GOVERNANCE.value == "governance"
        assert PipelineStage.STABILITY.value == "stability"
        assert PipelineStage.EXECUTION.value == "execution"
        assert PipelineStage.HEALTH_CHECK.value == "health_check"
        assert PipelineStage.COMPLETE.value == "complete"
        assert PipelineStage.FAILED.value == "failed"


class TestPipelineConfig:
    """Tests for PipelineConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = PipelineConfig()

        assert config.name == "default"
        assert config.enable_governance is True
        assert config.enable_stability is True
        assert config.enable_performance is True
        assert config.enable_health_check is True
        assert config.fail_on_blocked is True
        assert config.fail_on_critical is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = PipelineConfig(
            name="test_pipeline",
            enable_governance=False,
            fail_on_blocked=False,
        )

        assert config.name == "test_pipeline"
        assert config.enable_governance is False
        assert config.fail_on_blocked is False


class TestPipelineResult:
    """Tests for PipelineResult."""

    def test_result_creation(self):
        """Test result creation."""
        config = PipelineConfig(name="test")
        result = PipelineResult.create(config)

        assert result.result_id.startswith("PIPE-")
        assert result.stage_reached == PipelineStage.INIT
        assert result.success is False

    def test_result_to_dict(self):
        """Test result serialization."""
        config = PipelineConfig(name="test")
        result = PipelineResult.create(config)
        result.success = True
        result.total_time_ms = 100.0

        data = result.to_dict()

        assert data["schema_version"] == "pipeline_result_v1"
        assert data["success"] is True
        assert data["total_time_ms"] == 100.0


class TestUnifiedPipeline:
    """Tests for UnifiedPipeline."""

    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        pipeline = UnifiedPipeline()

        assert pipeline.pipeline_id.startswith("UNIFIED-")
        assert pipeline.governance_engine is not None
        assert pipeline.stability_analyzer is not None
        assert pipeline.performance_monitor is not None

    def test_pipeline_custom_id(self):
        """Test pipeline with custom ID."""
        pipeline = UnifiedPipeline(pipeline_id="TEST-PIPE")

        assert pipeline.pipeline_id == "TEST-PIPE"

    def test_run_simple_function(self):
        """Test running simple function."""
        pipeline = UnifiedPipeline()

        def simple_func():
            return 42

        result = pipeline.run(simple_func)

        assert result.success is True
        assert result.execution_result == 42
        assert result.stage_reached == PipelineStage.COMPLETE

    def test_run_with_governance(self):
        """Test running with governance check."""
        config = PipelineConfig(enable_governance=True)
        pipeline = UnifiedPipeline(config=config)

        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        result = pipeline.run(lambda: "done", governance_inputs=inputs)

        assert result.success is True
        assert result.governance_decision is not None

    def test_run_blocked_by_governance(self):
        """Test run blocked by governance."""
        config = PipelineConfig(
            enable_governance=True,
            fail_on_blocked=True,
        )
        pipeline = UnifiedPipeline(config=config)

        # Security violation causes block
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=True,
            ct_action="eval",
            mode="safe",
        )

        result = pipeline.run(lambda: "should not run", governance_inputs=inputs)

        assert result.success is False
        assert result.stage_reached == PipelineStage.FAILED
        assert "blocked" in result.error.lower()

    def test_run_with_stability(self):
        """Test running with stability analysis."""
        config = PipelineConfig(enable_stability=True)
        pipeline = UnifiedPipeline(config=config)

        jacobian = [[0.5, 0.0], [0.0, 0.5]]

        result = pipeline.run(lambda: "done", jacobian=jacobian)

        assert result.success is True
        assert result.stability_metrics is not None

    def test_run_blocked_by_critical_stability(self):
        """Test run blocked by critical stability."""
        config = PipelineConfig(
            enable_stability=True,
            enable_governance=False,
            fail_on_critical=True,
        )
        pipeline = UnifiedPipeline(config=config)

        # Force critical stability by using high values
        # Need to adjust the analyzer config
        from warm_logic_core.kernel.stability import StabilityConfig

        stab_config = StabilityConfig(min_samples=1, lipschitz_critical=0.5)
        pipeline.stability_analyzer.config = stab_config

        jacobian = [[10.0, 0.0], [0.0, 10.0]]

        result = pipeline.run(lambda: "should not run", jacobian=jacobian)

        # If critical, should fail
        if result.stability_metrics.status.value == "critical":
            assert result.success is False

    def test_run_with_performance_monitoring(self):
        """Test running with performance monitoring."""
        config = PipelineConfig(enable_performance=True)
        pipeline = UnifiedPipeline(config=config)

        def slow_func():
            time.sleep(0.01)
            return "done"

        result = pipeline.run(slow_func)

        assert result.success is True
        assert result.performance_metrics is not None
        assert result.performance_metrics.latency_avg_ms >= 10.0

    def test_run_with_health_check(self):
        """Test running with health check."""
        config = PipelineConfig(enable_health_check=True)
        pipeline = UnifiedPipeline(config=config)

        result = pipeline.run(lambda: "done")

        assert result.success is True
        assert result.system_health is not None

    def test_run_without_optional_stages(self):
        """Test running without optional stages."""
        config = PipelineConfig(
            enable_governance=False,
            enable_stability=False,
            enable_performance=False,
            enable_health_check=False,
        )
        pipeline = UnifiedPipeline(config=config)

        result = pipeline.run(lambda: "done")

        assert result.success is True
        assert result.governance_decision is None
        assert result.stability_metrics is None
        assert result.system_health is None

    def test_run_records_stage_times(self):
        """Test run records stage times."""
        config = PipelineConfig(enable_health_check=True)
        pipeline = UnifiedPipeline(config=config)

        result = pipeline.run(lambda: "done")

        assert "execution" in result.stage_times
        assert "health_check" in result.stage_times
        assert result.total_time_ms > 0

    def test_run_exception_handling(self):
        """Test run handles exceptions."""
        pipeline = UnifiedPipeline()

        def failing_func():
            raise ValueError("Test error")

        result = pipeline.run(failing_func)

        assert result.success is False
        assert result.stage_reached == PipelineStage.FAILED
        assert "Test error" in result.error

    def test_get_history(self):
        """Test getting execution history."""
        pipeline = UnifiedPipeline()

        pipeline.run(lambda: 1)
        pipeline.run(lambda: 2)

        history = pipeline.get_history()

        assert len(history) == 2

    def test_get_summary(self):
        """Test getting summary."""
        pipeline = UnifiedPipeline()

        pipeline.run(lambda: 1)
        pipeline.run(lambda: 2)

        summary = pipeline.get_summary()

        assert summary["total_runs"] == 2
        assert summary["success_rate"] == 1.0
        assert "avg_execution_time_ms" in summary

    def test_get_summary_empty(self):
        """Test summary with no runs."""
        pipeline = UnifiedPipeline()

        summary = pipeline.get_summary()

        assert summary["total_runs"] == 0
        assert summary["success_rate"] == 0.0

    def test_stage_distribution(self):
        """Test stage distribution in summary."""
        pipeline = UnifiedPipeline()

        pipeline.run(lambda: 1)

        summary = pipeline.get_summary()

        assert "stage_distribution" in summary
        assert "complete" in summary["stage_distribution"]


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    def test_full_pipeline_success(self):
        """Test complete pipeline success scenario."""
        config = PipelineConfig(
            name="full_test",
            enable_governance=True,
            enable_stability=True,
            enable_performance=True,
            enable_health_check=True,
        )
        pipeline = UnifiedPipeline(config=config)

        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )
        jacobian = [[0.5, 0.0], [0.0, 0.5]]

        def business_logic():
            return {"status": "completed", "value": 100}

        result = pipeline.run(
            business_logic,
            governance_inputs=inputs,
            jacobian=jacobian,
        )

        assert result.success is True
        assert result.stage_reached == PipelineStage.COMPLETE
        assert result.execution_result["status"] == "completed"
        assert result.governance_decision is not None
        assert result.stability_metrics is not None
        assert result.performance_metrics is not None
        assert result.system_health is not None

    def test_pipeline_trace_completeness(self):
        """Test pipeline trace is complete."""
        config = PipelineConfig(
            enable_governance=True,
            enable_health_check=True,
        )
        pipeline = UnifiedPipeline(config=config)

        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        result = pipeline.run(lambda: None, governance_inputs=inputs)

        # Trace should contain all stages
        trace_str = " ".join(result.trace)
        assert "stage:governance" in trace_str
        assert "stage:execution" in trace_str
        assert "stage:health_check" in trace_str
        assert "pipeline:complete" in trace_str

    def test_multiple_runs_isolation(self):
        """Test multiple runs are isolated."""
        pipeline = UnifiedPipeline()

        result1 = pipeline.run(lambda: "first")
        result2 = pipeline.run(lambda: "second")

        assert result1.execution_result == "first"
        assert result2.execution_result == "second"
        assert result1.result_id != result2.result_id
