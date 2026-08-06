"""Tests for Meta Governance Engine."""

from __future__ import annotations

import pytest

from warm_logic_core.governance.meta_governance_engine import (
    MetaGovernanceEngine,
    MetaGovernanceResult,
    MetaPolicy,
    run_meta_governance,
)


class TestMetaGovernanceResult:
    """Tests for MetaGovernanceResult."""

    def test_result_creation(self):
        """Test result creation."""
        result = MetaGovernanceResult.create()

        assert result.result_id.startswith("METAGOV-")
        assert result.governance_health == 1.0
        assert result.policy_compliance == 1.0

    def test_result_to_dict(self):
        """Test result serialization."""
        result = MetaGovernanceResult.create()
        data = result.to_dict()

        assert data["schema_version"] == "meta_governance_result_v1"
        assert "governance_health" in data
        assert "policy_compliance" in data

    def test_is_healthy_true(self):
        """Test is_healthy returns True for healthy state."""
        result = MetaGovernanceResult(
            result_id="TEST",
            governance_health=0.9,
            policy_compliance=0.95,
        )

        assert result.is_healthy() is True

    def test_is_healthy_false_low_health(self):
        """Test is_healthy returns False for low health."""
        result = MetaGovernanceResult(
            result_id="TEST",
            governance_health=0.5,
            policy_compliance=0.95,
        )

        assert result.is_healthy() is False

    def test_is_healthy_false_low_compliance(self):
        """Test is_healthy returns False for low compliance."""
        result = MetaGovernanceResult(
            result_id="TEST",
            governance_health=0.9,
            policy_compliance=0.6,
        )

        assert result.is_healthy() is False


class TestMetaPolicy:
    """Tests for MetaPolicy."""

    def test_default_policy(self):
        """Test default policy values."""
        policy = MetaPolicy()

        assert policy.name == "default_meta_policy"
        assert policy.min_health_threshold == 0.7
        assert policy.min_compliance_threshold == 0.8
        assert policy.anomaly_limit == 5

    def test_custom_policy(self):
        """Test custom policy values."""
        policy = MetaPolicy(
            name="strict_policy",
            min_health_threshold=0.9,
            min_compliance_threshold=0.95,
            anomaly_limit=2,
        )

        assert policy.name == "strict_policy"
        assert policy.min_health_threshold == 0.9


class TestMetaGovernanceEngine:
    """Tests for MetaGovernanceEngine."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = MetaGovernanceEngine()

        assert engine.engine_id.startswith("METAENG-")
        assert len(engine.history) == 0

    def test_engine_with_custom_id(self):
        """Test engine with custom ID."""
        engine = MetaGovernanceEngine(engine_id="METAENG-CUSTOM")

        assert engine.engine_id == "METAENG-CUSTOM"

    def test_engine_with_custom_policy(self):
        """Test engine with custom meta policy."""
        policy = MetaPolicy(min_health_threshold=0.9)
        engine = MetaGovernanceEngine(meta_policy=policy)

        assert engine.meta_policy.min_health_threshold == 0.9

    def test_evaluate_empty(self):
        """Test evaluating with no recorded decisions."""
        engine = MetaGovernanceEngine()

        result = engine.evaluate()

        assert result.governance_health == 1.0
        assert result.policy_compliance == 1.0
        assert len(result.anomalies_detected) == 0

    def test_record_and_evaluate(self):
        """Test recording decisions and evaluating."""
        engine = MetaGovernanceEngine()

        for i in range(10):
            engine.record_decision(
                {
                    "govSAT": "SatAllow" if i < 8 else "SatBlock",
                    "reason": "test",
                }
            )

        result = engine.evaluate()

        assert result.governance_health >= 0.7
        assert len(result.anomalies_detected) == 0

    def test_high_block_rate_detected(self):
        """Test high block rate is detected as anomaly."""
        engine = MetaGovernanceEngine()

        for i in range(10):
            engine.record_decision(
                {
                    "govSAT": "SatBlock" if i < 5 else "SatAllow",
                    "reason": "test",
                }
            )

        result = engine.evaluate()

        assert "high_block_rate" in result.anomalies_detected

    def test_missing_reasons_detected(self):
        """Test missing reasons are detected."""
        engine = MetaGovernanceEngine()

        for i in range(5):
            engine.record_decision(
                {
                    "govSAT": "SatAllow",
                    "reason": "" if i < 2 else "test",
                }
            )

        result = engine.evaluate()

        assert any("missing_reasons" in a for a in result.anomalies_detected)

    def test_recommendations_generated(self):
        """Test recommendations are generated for issues."""
        engine = MetaGovernanceEngine()

        # Create high block rate
        for i in range(10):
            engine.record_decision(
                {
                    "govSAT": "SatBlock",
                    "reason": "test",
                }
            )

        result = engine.evaluate()

        assert len(result.recommendations) > 0

    def test_history_recorded(self):
        """Test evaluation history is recorded."""
        engine = MetaGovernanceEngine()

        engine.evaluate()
        engine.evaluate()
        engine.evaluate()

        assert len(engine.history) == 3

    def test_get_trend_stable(self):
        """Test trend calculation for stable history."""
        engine = MetaGovernanceEngine()

        for _ in range(5):
            engine.evaluate()

        trend = engine.get_trend()

        assert trend["direction"] == "stable"

    def test_get_trend_insufficient_history(self):
        """Test trend with insufficient history."""
        engine = MetaGovernanceEngine()

        trend = engine.get_trend()

        assert trend["direction"] == "stable"
        assert trend["magnitude"] == 0.0

    def test_clear_history(self):
        """Test clearing history."""
        engine = MetaGovernanceEngine()

        engine.record_decision({"govSAT": "SatAllow", "reason": "test"})
        engine.evaluate()

        engine.clear_history()

        assert len(engine.history) == 0
        assert len(engine._decision_history) == 0

    def test_metrics_calculated(self):
        """Test metrics are calculated."""
        engine = MetaGovernanceEngine()

        for i in range(5):
            engine.record_decision(
                {
                    "govSAT": "SatAllow" if i % 2 == 0 else "SatBlock",
                    "reason": "test",
                }
            )

        result = engine.evaluate()

        assert result.metrics["total_decisions"] == 5
        assert "sat_distribution" in result.metrics


class TestRunMetaGovernance:
    """Tests for run_meta_governance function."""

    def test_run_meta_governance(self):
        """Test running meta governance."""
        result = run_meta_governance()

        assert result["schema_version"] == "meta_governance_result_v1"
        assert "governance_health" in result
        assert "policy_compliance" in result
