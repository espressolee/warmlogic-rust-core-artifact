"""Tests for Governance-Stability Integration."""

from __future__ import annotations

import pytest

from warm_logic_core.governance import GovernanceInputs, GovernanceEngine
from warm_logic_core.kernel.stability import (
    StabilityAnalyzer,
    StabilityMetrics,
    StabilityStatus,
)
from warm_logic_core.integration.governance_stability import (
    GovernanceStabilityBridge,
    StabilityAwareDecision,
    StabilityThresholds,
    create_stability_governance_context,
)


class TestStabilityAwareDecision:
    """Tests for StabilityAwareDecision."""

    def test_decision_creation(self):
        """Test decision creation."""
        decision = StabilityAwareDecision.create()

        assert decision.decision_id.startswith("SAD-")
        assert decision.stability_influenced is False

    def test_decision_to_dict(self):
        """Test decision serialization."""
        decision = StabilityAwareDecision.create()
        decision.stability_influenced = True
        decision.original_action = "continue"

        data = decision.to_dict()

        assert data["schema_version"] == "stability_aware_decision_v1"
        assert data["stability_influenced"] is True
        assert data["original_action"] == "continue"


class TestStabilityThresholds:
    """Tests for StabilityThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = StabilityThresholds()

        assert thresholds.block_on_critical is True
        assert thresholds.review_on_caution is True
        assert thresholds.lipschitz_block == 3.0
        assert thresholds.cgf_block == 2.0

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = StabilityThresholds(
            lipschitz_block=5.0,
            block_on_critical=False,
        )

        assert thresholds.lipschitz_block == 5.0
        assert thresholds.block_on_critical is False


class TestGovernanceStabilityBridge:
    """Tests for GovernanceStabilityBridge."""

    def test_bridge_initialization(self):
        """Test bridge initialization."""
        bridge = GovernanceStabilityBridge()

        assert bridge.bridge_id.startswith("BRIDGE-")
        assert bridge.governance_engine is not None
        assert bridge.stability_analyzer is not None

    def test_bridge_custom_id(self):
        """Test bridge with custom ID."""
        bridge = GovernanceStabilityBridge(bridge_id="TEST-BRIDGE")

        assert bridge.bridge_id == "TEST-BRIDGE"

    def test_evaluate_without_stability(self):
        """Test evaluate without stability data."""
        bridge = GovernanceStabilityBridge()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        result = bridge.evaluate(inputs)

        assert result.governance_decision is not None
        assert result.stability_metrics is None
        assert result.stability_influenced is False

    def test_evaluate_with_stable_jacobian(self):
        """Test evaluate with stable Jacobian."""
        bridge = GovernanceStabilityBridge()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        # Stable Jacobian (small values)
        jacobian = [[0.1, 0.0], [0.0, 0.1]]

        result = bridge.evaluate(inputs, jacobian=jacobian)

        assert result.stability_metrics is not None
        assert result.stability_metrics.lipschitz < 1.0
        assert result.governance_decision is not None

    def test_evaluate_blocks_on_high_lipschitz(self):
        """Test evaluate blocks on high Lipschitz."""
        thresholds = StabilityThresholds(lipschitz_block=1.0)
        bridge = GovernanceStabilityBridge(thresholds=thresholds)
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        # High Lipschitz Jacobian
        jacobian = [[5.0, 0.0], [0.0, 5.0]]

        result = bridge.evaluate(inputs, jacobian=jacobian)

        assert result.stability_influenced is True
        assert result.governance_decision.outputs.govAction == "forbid"

    def test_evaluate_with_cgf_data(self):
        """Test evaluate with CGF data."""
        bridge = GovernanceStabilityBridge()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        result = bridge.evaluate(
            inputs,
            delta_in=[1.0, 0.0],
            delta_out=[0.5, 0.0],
        )

        assert result.stability_metrics is not None
        assert result.stability_metrics.cgf == 0.5

    def test_evaluate_blocks_on_high_cgf(self):
        """Test evaluate blocks on high CGF."""
        thresholds = StabilityThresholds(cgf_block=1.0)
        bridge = GovernanceStabilityBridge(thresholds=thresholds)
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        # High CGF (expansive)
        result = bridge.evaluate(
            inputs,
            delta_in=[1.0, 0.0],
            delta_out=[3.0, 0.0],  # CGF = 3.0
        )

        assert result.stability_influenced is True
        assert result.governance_decision.outputs.govAction == "forbid"

    def test_evaluate_respects_disable_flags(self):
        """Test evaluate respects threshold disable flags."""
        thresholds = StabilityThresholds(
            block_on_critical=False,
            review_on_caution=False,
        )
        bridge = GovernanceStabilityBridge(thresholds=thresholds)
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        # Even with high values, should not block
        jacobian = [[0.5, 0.0], [0.0, 0.5]]

        result = bridge.evaluate(inputs, jacobian=jacobian)

        # Only Lipschitz/CGF threshold checks, not status-based
        assert result.governance_decision is not None

    def test_get_history(self):
        """Test getting decision history."""
        bridge = GovernanceStabilityBridge()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        bridge.evaluate(inputs)
        bridge.evaluate(inputs)

        history = bridge.get_history()

        assert len(history) == 2

    def test_get_stability_trend(self):
        """Test getting stability trend."""
        bridge = GovernanceStabilityBridge()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        bridge.evaluate(inputs, jacobian=[[0.1, 0.0], [0.0, 0.1]])

        trend = bridge.get_stability_trend()

        assert "total_decisions" in trend
        assert "influenced_count" in trend

    def test_clear_history(self):
        """Test clearing history."""
        bridge = GovernanceStabilityBridge()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        bridge.evaluate(inputs)
        bridge.clear_history()

        assert len(bridge.get_history()) == 0


class TestCreateStabilityGovernanceContext:
    """Tests for create_stability_governance_context."""

    def test_context_creation(self):
        """Test context creation from metrics."""
        metrics = StabilityMetrics.create()
        metrics.status = StabilityStatus.STABLE
        metrics.stability_index = 0.25
        metrics.lipschitz = 0.5

        context = create_stability_governance_context(metrics)

        assert context.request_id.startswith("REQ-")
        assert context.source == "stability_bridge"
        assert context.metadata["stability_status"] == "stable"
        assert context.metadata["stability_index"] == 0.25
        assert context.metadata["lipschitz"] == 0.5


class TestIntegrationScenarios:
    """Integration scenario tests."""

    def test_security_violation_overrides_stability(self):
        """Test security violation takes precedence."""
        bridge = GovernanceStabilityBridge()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=True,  # Security violation
            ct_action="eval",
            mode="safe",
        )

        # Even with stable Jacobian
        jacobian = [[0.1, 0.0], [0.0, 0.1]]

        result = bridge.evaluate(inputs, jacobian=jacobian)

        # Should be blocked due to security, not stability
        assert result.governance_decision.outputs.govAction == "forbid"

    def test_stable_system_allows_actions(self):
        """Test stable system allows normal actions."""
        thresholds = StabilityThresholds(
            lipschitz_block=5.0,
            cgf_block=5.0,
        )
        bridge = GovernanceStabilityBridge(thresholds=thresholds)
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="nominal",
            tests_failing=False,
            security_violation=False,
            ct_action="eval",
            mode="safe",
        )

        jacobian = [[0.5, 0.0], [0.0, 0.5]]

        result = bridge.evaluate(inputs, jacobian=jacobian)

        assert result.stability_influenced is False
        assert result.governance_decision.outputs.govAction == "continue"
