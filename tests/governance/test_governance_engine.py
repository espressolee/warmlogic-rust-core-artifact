"""Tests for Governance Engine."""

from __future__ import annotations

import pytest

from warm_logic_core.governance.gov_inputs import GovernanceInputs
from warm_logic_core.governance.gov_outputs import GovernanceOutputs
from warm_logic_core.governance.governance_engine import (
    GovernanceEngine,
    GovernanceDecision,
    DecisionContext,
    GovernancePolicy,
)


class TestDecisionContext:
    """Tests for DecisionContext."""

    def test_context_creation(self):
        """Test context creation."""
        ctx = DecisionContext.create(
            source="api",
            actor="user-123",
            target="resource-456",
        )

        assert ctx.request_id.startswith("REQ-")
        assert ctx.source == "api"
        assert ctx.actor == "user-123"

    def test_context_to_dict(self):
        """Test context serialization."""
        ctx = DecisionContext.create()
        data = ctx.to_dict()

        assert "request_id" in data
        assert "timestamp" in data
        assert "source" in data


class TestGovernanceDecision:
    """Tests for GovernanceDecision."""

    def test_decision_creation(self):
        """Test decision creation."""
        inputs = GovernanceInputs.default()
        outputs = GovernanceOutputs.allow("ok")
        ctx = DecisionContext.create()

        decision = GovernanceDecision.create(
            decision_type="allow",
            inputs=inputs,
            outputs=outputs,
            context=ctx,
        )

        assert decision.decision_id.startswith("DEC-")
        assert decision.decision_type == "allow"
        assert decision.outputs.govSAT == "SatAllow"

    def test_decision_to_dict(self):
        """Test decision serialization."""
        inputs = GovernanceInputs.default()
        outputs = GovernanceOutputs.allow("ok")
        ctx = DecisionContext.create()

        decision = GovernanceDecision.create(
            decision_type="allow",
            inputs=inputs,
            outputs=outputs,
            context=ctx,
        )

        data = decision.to_dict()

        assert data["schema_version"] == "governance_decision_v1"
        assert data["decision_type"] == "allow"
        assert "inputs" in data
        assert "outputs" in data


class TestGovernancePolicy:
    """Tests for GovernancePolicy."""

    def test_policy_creation(self):
        """Test policy creation."""
        policy = GovernancePolicy(
            name="test_policy",
            version="1.0.0",
            description="Test policy",
            rules={"max_risk": 0.5},
        )

        assert policy.name == "test_policy"
        assert policy.enabled is True

    def test_policy_to_dict(self):
        """Test policy serialization."""
        policy = GovernancePolicy(name="test")
        data = policy.to_dict()

        assert data["name"] == "test"
        assert data["enabled"] is True


class TestGovernanceEngine:
    """Tests for GovernanceEngine."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = GovernanceEngine()

        assert engine.engine_id.startswith("GOVENG-")
        assert len(engine.policies) == 0
        assert len(engine.decisions) == 0

    def test_engine_with_custom_id(self):
        """Test engine with custom ID."""
        engine = GovernanceEngine(engine_id="GOVENG-CUSTOM001")

        assert engine.engine_id == "GOVENG-CUSTOM001"

    def test_engine_start_stop(self):
        """Test engine start/stop."""
        engine = GovernanceEngine()

        assert engine.is_running() is False

        engine.start()
        assert engine.is_running() is True

        engine.stop()
        assert engine.is_running() is False

    def test_add_policy(self):
        """Test adding policy."""
        engine = GovernanceEngine()
        policy = GovernancePolicy(name="test_policy")

        engine.add_policy(policy)

        assert len(engine.policies) == 1
        assert engine.policies[0].name == "test_policy"

    def test_remove_policy(self):
        """Test removing policy."""
        engine = GovernanceEngine()
        policy = GovernancePolicy(name="test_policy")
        engine.add_policy(policy)

        result = engine.remove_policy("test_policy")

        assert result is True
        assert len(engine.policies) == 0

    def test_remove_nonexistent_policy(self):
        """Test removing nonexistent policy."""
        engine = GovernanceEngine()

        result = engine.remove_policy("nonexistent")

        assert result is False

    def test_evaluate_default_inputs(self):
        """Test evaluating default inputs."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs.default()

        decision = engine.evaluate(inputs)

        assert decision.decision_type == "allow"
        assert decision.outputs.govSAT == "SatAllow"
        assert len(decision.trace) > 0

    def test_evaluate_with_context(self):
        """Test evaluating with context."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs.default()
        ctx = DecisionContext.create(source="test", actor="test_user")

        decision = engine.evaluate(inputs, context=ctx)

        assert decision.context.source == "test"
        assert decision.context.actor == "test_user"

    def test_evaluate_security_violation(self):
        """Test evaluating security violation."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=True,
            ct_action="noop",
            mode="safe",
        )

        decision = engine.evaluate(inputs)

        assert decision.decision_type == "block"
        assert decision.outputs.govSAT == "SatBlock"

    def test_evaluate_drift_alarm(self):
        """Test evaluating drift alarm."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs(
            drift_alarm=True,
            drift_regime="volatile",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
        )

        decision = engine.evaluate(inputs)

        assert decision.decision_type == "review"
        assert decision.outputs.govSAT == "SatReview"

    def test_decisions_recorded(self):
        """Test decisions are recorded."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs.default()

        engine.evaluate(inputs)
        engine.evaluate(inputs)
        engine.evaluate(inputs)

        assert len(engine.decisions) == 3

    def test_get_recent_decisions(self):
        """Test getting recent decisions."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs.default()

        for _ in range(20):
            engine.evaluate(inputs)

        recent = engine.get_recent_decisions(limit=5)

        assert len(recent) == 5

    def test_clear_decisions(self):
        """Test clearing decisions."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs.default()

        engine.evaluate(inputs)
        engine.evaluate(inputs)

        engine.clear_decisions()

        assert len(engine.decisions) == 0

    def test_hook_called(self):
        """Test decision hook is called."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs.default()

        called = []

        def hook(decision):
            called.append(decision)

        engine.add_hook(hook)
        engine.evaluate(inputs)

        assert len(called) == 1
        assert called[0].decision_type == "allow"

    def test_hook_error_ignored(self):
        """Test hook errors are ignored."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs.default()

        def bad_hook(decision):
            raise ValueError("Hook error")

        engine.add_hook(bad_hook)
        decision = engine.evaluate(inputs)

        # Should not raise, decision should succeed
        assert decision.decision_type == "allow"

    def test_get_stats(self):
        """Test getting engine statistics."""
        engine = GovernanceEngine()
        inputs_allow = GovernanceInputs.default()
        inputs_block = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=True,
            security_violation=False,
            ct_action="noop",
            mode="safe",
        )

        engine.evaluate(inputs_allow)
        engine.evaluate(inputs_allow)
        engine.evaluate(inputs_block)

        stats = engine.get_stats()

        assert stats["total_decisions"] == 3
        assert stats["decisions_by_type"]["allow"] == 2
        assert stats["decisions_by_type"]["block"] == 1

    def test_rstar_override_applied(self):
        """Test R* override is applied."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=0.1,  # Very low, should block
        )

        decision = engine.evaluate(inputs)

        assert decision.decision_type == "block"
        assert "rstar_block" in decision.outputs.reason

    def test_trace_contains_steps(self):
        """Test trace contains evaluation steps."""
        engine = GovernanceEngine()
        inputs = GovernanceInputs.default()

        decision = engine.evaluate(inputs)

        assert "engine_id=" in decision.trace[0]
        assert any("eval_vm" in t for t in decision.trace)
        assert any("rstar_overrides" in t for t in decision.trace)
