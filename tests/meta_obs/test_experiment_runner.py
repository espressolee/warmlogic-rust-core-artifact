"""Tests for ExperimentRunner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from warm_logic_core.meta_obs.experiment_runner import (
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentOutcome,
    ExperimentResult,
    ExperimentRunner,
    ExperimentStatus,
    ExperimentType,
    Hypothesis,
)


class TestExperimentConfig:
    """Tests for ExperimentConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ExperimentConfig(experiment_type=ExperimentType.AB_TEST)

        assert config.experiment_type == ExperimentType.AB_TEST
        assert config.duration_hours == 1.0
        assert config.sample_size == 100
        assert config.traffic_percentage == 10.0
        assert config.control_variant_id == "control"
        assert config.treatment_variant_id == "treatment"
        assert config.auto_rollback_enabled is True

    def test_config_to_dict(self):
        """Test config serialization."""
        config = ExperimentConfig(
            experiment_type=ExperimentType.CANARY,
            duration_hours=24.0,
            sample_size=1000,
        )

        data = config.to_dict()

        assert data["duration_hours"] == 24.0
        assert data["sample_size"] == 1000
        assert "control_group" in data
        assert "treatment_group" in data


class TestHypothesis:
    """Tests for Hypothesis."""

    def test_hypothesis_creation(self):
        """Test hypothesis creation."""
        hypothesis = Hypothesis(
            statement="Treatment reduces latency by 10%",
            expected_outcome="Lower latency in treatment group",
            success_criteria=[
                {"metric": "latency_p99", "operator": "<", "threshold": 100}
            ],
        )

        assert hypothesis.statement == "Treatment reduces latency by 10%"
        assert len(hypothesis.success_criteria) == 1

    def test_hypothesis_to_dict(self):
        """Test hypothesis serialization."""
        hypothesis = Hypothesis(
            statement="Test hypothesis",
            expected_outcome="Expected outcome",
        )

        data = hypothesis.to_dict()

        assert data["statement"] == "Test hypothesis"
        assert data["expected_outcome"] == "Expected outcome"


class TestExperimentMetrics:
    """Tests for ExperimentMetrics."""

    def test_metrics_creation(self):
        """Test metrics creation."""
        metrics = ExperimentMetrics(
            control_metrics={"latency_p99": 100, "error_rate": 0.01},
            treatment_metrics={"latency_p99": 90, "error_rate": 0.008},
            p_value=0.03,
            confidence_level=0.95,
            effect_size=-0.1,
        )

        assert metrics.control_metrics["latency_p99"] == 100
        assert metrics.treatment_metrics["latency_p99"] == 90
        assert metrics.p_value == 0.03

    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        metrics = ExperimentMetrics(
            control_metrics={"throughput": 1000},
            treatment_metrics={"throughput": 1100},
        )

        data = metrics.to_dict()

        assert "control_metrics" in data
        assert "treatment_metrics" in data
        assert "statistical_significance" in data


class TestExperimentResult:
    """Tests for ExperimentResult."""

    def test_result_creation(self):
        """Test result creation."""
        result = ExperimentResult(
            experiment_id="EXP-TEST001",
            status=ExperimentStatus.COMPLETED,
            outcome=ExperimentOutcome.SUCCESS,
            summary="Experiment completed successfully",
        )

        assert result.experiment_id == "EXP-TEST001"
        assert result.status == ExperimentStatus.COMPLETED
        assert result.outcome == ExperimentOutcome.SUCCESS

    def test_result_with_metrics(self):
        """Test result with metrics."""
        metrics = ExperimentMetrics(
            control_metrics={"latency": 100},
            treatment_metrics={"latency": 95},
        )
        result = ExperimentResult(
            experiment_id="EXP-TEST002",
            status=ExperimentStatus.COMPLETED,
            outcome=ExperimentOutcome.SUCCESS,
            metrics=metrics,
        )

        data = result.to_dict()

        assert data["control_metrics"]["latency"] == 100
        assert data["treatment_metrics"]["latency"] == 95


class TestExperiment:
    """Tests for Experiment."""

    def test_experiment_creation(self):
        """Test experiment creation."""
        config = ExperimentConfig(experiment_type=ExperimentType.AB_TEST)
        experiment = Experiment(
            experiment_id="EXP-TEST003",
            experiment_type=ExperimentType.AB_TEST,
            config=config,
        )

        assert experiment.experiment_id == "EXP-TEST003"
        assert experiment.status == ExperimentStatus.PENDING
        assert experiment.started_at is None
        assert experiment.completed_at is None

    def test_experiment_to_dict(self):
        """Test experiment serialization."""
        config = ExperimentConfig(
            experiment_type=ExperimentType.SHADOW,
            component="governance_engine",
            version="1.0.0",
            environment="staging",
        )
        experiment = Experiment(
            experiment_id="EXP-TEST004",
            experiment_type=ExperimentType.SHADOW,
            config=config,
            owner="test_user",
            tags=["shadow", "governance"],
        )

        data = experiment.to_dict()

        assert data["schema_version"] == "meta_obs_experiment_v1"
        assert data["experiment_id"] == "EXP-TEST004"
        assert data["experiment_type"] == "shadow"
        assert data["status"] == "pending"
        assert data["target"]["component"] == "governance_engine"
        assert data["owner"] == "test_user"


class TestExperimentRunner:
    """Tests for ExperimentRunner."""

    def test_runner_initialization(self):
        """Test runner initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)

            assert runner.artifacts_dir == Path(tmpdir)
            assert runner.auto_persist is False

    def test_create_experiment(self):
        """Test experiment creation via runner."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(experiment_type=ExperimentType.AB_TEST)

            experiment = runner.create_experiment(
                config=config, owner="test_user", tags=["test"]
            )

            assert experiment.experiment_id.startswith("EXP-")
            assert experiment.status == ExperimentStatus.PENDING
            assert experiment.owner == "test_user"

    def test_create_experiment_with_custom_id(self):
        """Test experiment creation with custom ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(experiment_type=ExperimentType.VALIDATION)

            experiment = runner.create_experiment(
                config=config, experiment_id="EXP-CUSTOM001"
            )

            assert experiment.experiment_id == "EXP-CUSTOM001"

    def test_start_experiment(self):
        """Test starting an experiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(experiment_type=ExperimentType.AB_TEST)
            experiment = runner.create_experiment(config=config)

            runner.start_experiment(experiment.experiment_id)

            updated = runner.get_experiment(experiment.experiment_id)
            assert updated.status == ExperimentStatus.RUNNING
            assert updated.started_at is not None

    def test_start_already_running_experiment(self):
        """Test starting an already running experiment fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(experiment_type=ExperimentType.AB_TEST)
            experiment = runner.create_experiment(config=config)
            runner.start_experiment(experiment.experiment_id)

            with pytest.raises(ValueError, match="Cannot start experiment"):
                runner.start_experiment(experiment.experiment_id)

    def test_run_experiment_with_default_handler(self):
        """Test running experiment with default handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(
                experiment_type=ExperimentType.AB_TEST, duration_hours=0.0001
            )
            experiment = runner.create_experiment(config=config)

            result = runner.run_experiment(experiment.experiment_id)

            assert result.status == ExperimentStatus.COMPLETED
            assert result.outcome is not None
            assert result.metrics is not None

    def test_run_experiment_with_custom_handler(self):
        """Test running experiment with custom handler."""

        def custom_handler(exp: Experiment) -> ExperimentResult:
            return ExperimentResult(
                experiment_id=exp.experiment_id,
                status=ExperimentStatus.COMPLETED,
                outcome=ExperimentOutcome.SUCCESS,
                summary="Custom handler result",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(experiment_type=ExperimentType.VALIDATION)
            experiment = runner.create_experiment(config=config)

            result = runner.run_experiment(
                experiment.experiment_id, handler=custom_handler
            )

            assert result.outcome == ExperimentOutcome.SUCCESS
            assert result.summary == "Custom handler result"

    def test_cancel_experiment(self):
        """Test canceling an experiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(experiment_type=ExperimentType.AB_TEST)
            experiment = runner.create_experiment(config=config)

            runner.cancel_experiment(experiment.experiment_id)

            updated = runner.get_experiment(experiment.experiment_id)
            assert updated.status == ExperimentStatus.CANCELLED

    def test_pause_experiment(self):
        """Test pausing an experiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(experiment_type=ExperimentType.AB_TEST)
            experiment = runner.create_experiment(config=config)
            runner.start_experiment(experiment.experiment_id)

            runner.pause_experiment(experiment.experiment_id)

            updated = runner.get_experiment(experiment.experiment_id)
            assert updated.status == ExperimentStatus.PAUSED

    def test_list_experiments(self):
        """Test listing experiments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)

            config1 = ExperimentConfig(experiment_type=ExperimentType.AB_TEST)
            config2 = ExperimentConfig(experiment_type=ExperimentType.CANARY)

            runner.create_experiment(config=config1)
            runner.create_experiment(config=config2)

            all_experiments = runner.list_experiments()
            ab_tests = runner.list_experiments(experiment_type=ExperimentType.AB_TEST)

            assert len(all_experiments) == 2
            assert len(ab_tests) == 1

    def test_persist_and_load_experiment(self):
        """Test persisting and loading experiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=True)
            config = ExperimentConfig(
                experiment_type=ExperimentType.AB_TEST,
                hypothesis=Hypothesis(
                    statement="Test hypothesis",
                    expected_outcome="Expected outcome",
                ),
            )

            experiment = runner.create_experiment(
                config=config, experiment_id="EXP-PERSIST001"
            )

            # Create new runner and load
            runner2 = ExperimentRunner(artifacts_dir=tmpdir)
            loaded = runner2.load_experiment("EXP-PERSIST001")

            assert loaded is not None
            assert loaded.experiment_id == "EXP-PERSIST001"
            assert loaded.experiment_type == ExperimentType.AB_TEST

    def test_register_handler(self):
        """Test registering a handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)

            def my_handler(exp: Experiment) -> ExperimentResult:
                return ExperimentResult(
                    experiment_id=exp.experiment_id,
                    status=ExperimentStatus.COMPLETED,
                    outcome=ExperimentOutcome.SUCCESS,
                )

            runner.register_handler(ExperimentType.STRESS_TEST, my_handler)

            config = ExperimentConfig(experiment_type=ExperimentType.STRESS_TEST)
            experiment = runner.create_experiment(config=config)
            result = runner.run_experiment(experiment.experiment_id)

            assert result.outcome == ExperimentOutcome.SUCCESS

    def test_experiment_not_found(self):
        """Test error when experiment not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)

            with pytest.raises(ValueError, match="Experiment not found"):
                runner.start_experiment("EXP-NONEXISTENT")

    def test_rollback_detection(self):
        """Test rollback detection based on metrics."""

        def failing_handler(exp: Experiment) -> ExperimentResult:
            return ExperimentResult(
                experiment_id=exp.experiment_id,
                status=ExperimentStatus.COMPLETED,
                outcome=ExperimentOutcome.FAILURE,
                metrics=ExperimentMetrics(
                    control_metrics={"error_rate": 0.01},
                    treatment_metrics={"error_rate": 0.05},  # 5x increase
                ),
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(artifacts_dir=tmpdir, auto_persist=False)
            config = ExperimentConfig(
                experiment_type=ExperimentType.AB_TEST,
                auto_rollback_enabled=True,
                rollback_threshold=0.1,
            )

            experiment = runner.create_experiment(config=config)
            result = runner.run_experiment(
                experiment.experiment_id, handler=failing_handler
            )

            assert result.rollback_triggered is True
