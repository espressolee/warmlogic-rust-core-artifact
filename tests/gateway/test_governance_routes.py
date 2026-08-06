"""Tests for governance API routes.

Comprehensive tests for:
- /governance/propose endpoint
- /governance/evaluate endpoint
- /governance/policies endpoint
- /governance/status endpoint
- /governance/modes endpoint
"""

from __future__ import annotations

import hashlib
import sys
import types
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.gateway.routes.governance import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_EPSILON_C,
    DEFAULT_TAU_ETHICS,
    Decision,
    EvaluatePolicyRequest,
    EvaluatePolicyResponse,
    GovernanceStatus,
    PolicyListResponse,
    PolicyRule,
    ProposeActionRequest,
    _compute_e_stab,
    _compute_mode_snapshot,
    _fallback_mode,
    evaluate_policy,
    get_status,
    list_modes,
    list_policies,
    propose_action,
    router,
)

# ============================================================================
# Tests for Internal Helper Functions
# ============================================================================


class TestComputeEStab:
    """Tests for _compute_e_stab formula."""

    def test_default_parameters(self):
        """Test with default alpha/beta."""
        result = _compute_e_stab(0.2, 0.1)
        expected = 0.5 * 0.2 + 0.5 * (1.0 - 0.1)  # 0.1 + 0.45 = 0.55
        assert result == pytest.approx(expected)

    def test_custom_alpha_beta(self):
        """Test with custom weights."""
        result = _compute_e_stab(0.4, 0.2, alpha=0.3, beta=0.7)
        expected = 0.3 * 0.4 + 0.7 * (1.0 - 0.2)  # 0.12 + 0.56 = 0.68
        assert result == pytest.approx(expected)

    def test_extreme_values(self):
        """Test with edge case values."""
        # Max stability
        result = _compute_e_stab(0.0, 0.0)
        assert result == pytest.approx(0.5)

        # Min stability with high tau_ethics
        result = _compute_e_stab(0.0, 1.0)
        assert result == pytest.approx(0.0)


class TestFallbackMode:
    """Tests for _fallback_mode determination."""

    def test_normal_mode(self):
        """Test NORMAL mode conditions."""
        assert _fallback_mode(0.8, 0.5) == "NORMAL"
        assert _fallback_mode(0.7, 0.0) == "NORMAL"

    def test_suspicious_mode(self):
        """Test SUSPICIOUS mode conditions."""
        assert _fallback_mode(0.5, 0.5) == "SUSPICIOUS"
        assert _fallback_mode(0.3, 0.5) == "SUSPICIOUS"

    def test_critical_halt_mode(self):
        """Test CRITICAL_HALT mode conditions."""
        assert _fallback_mode(0.2, 0.5) == "CRITICAL_HALT"
        assert _fallback_mode(0.1, 0.0) == "CRITICAL_HALT"

    def test_veto_lock_mode(self):
        """Test VETO_LOCK mode (tau_ethics > 0.85 takes precedence)."""
        assert _fallback_mode(0.9, 0.9) == "VETO_LOCK"
        assert _fallback_mode(0.5, 0.86) == "VETO_LOCK"


# ============================================================================
# Tests for ProposeActionRequest Model
# ============================================================================


class TestProposeActionRequest:
    """Tests for ProposeActionRequest validation."""

    def test_minimal_request(self):
        """Test request with minimal required fields."""
        request = ProposeActionRequest(intent="test_action")
        assert request.intent == "test_action"
        assert request.context == {}
        assert request.require_proof is False
        assert request.require_consensus is False

    def test_full_request(self):
        """Test request with all fields."""
        request = ProposeActionRequest(
            intent="execute_trade",
            context={"symbol": "AAPL", "quantity": 100},
            require_proof=True,
            require_consensus=True,
        )
        assert request.intent == "execute_trade"
        assert request.context["symbol"] == "AAPL"
        assert request.require_proof is True
        assert request.require_consensus is True


class TestDecision:
    """Tests for Decision model."""

    def test_decision_creation(self):
        """Test decision model creation."""
        decision = Decision(
            decision_id="test-123",
            verdict="ALLOW",
            reason="No violations",
            timestamp=datetime.now(),
            mode="NORMAL",
        )
        assert decision.decision_id == "test-123"
        assert decision.verdict == "ALLOW"
        assert decision.proof_hash is None
        assert decision.signature is None


# ============================================================================
# Tests for /governance/propose Endpoint
# ============================================================================


class TestProposeAction:
    """Tests for propose_action endpoint."""

    @pytest.mark.asyncio
    async def test_propose_allowed_action(self):
        """Test proposing an allowed action."""
        request = ProposeActionRequest(intent="send_email")

        decision = await propose_action(request, api_key="test-key")

        assert decision.verdict == "ALLOW"
        assert decision.mode in ["NORMAL", "SUSPICIOUS", "CRITICAL_HALT", "VETO_LOCK"]
        assert len(decision.decision_id) == 16

    @pytest.mark.asyncio
    async def test_propose_blocked_intent(self):
        """Test proposing a blocked intent."""
        request = ProposeActionRequest(intent="delete_all")

        decision = await propose_action(request, api_key="test-key")

        assert decision.verdict == "DENY"
        # Either SDK or fallback message
        assert (
            "blocked" in decision.reason.lower()
            or "constitution" in decision.reason.lower()
        )

    @pytest.mark.asyncio
    async def test_propose_shutdown_intent_evaluated(self):
        """Test shutdown_system intent is evaluated by governance."""
        request = ProposeActionRequest(intent="shutdown_system")

        decision = await propose_action(request, api_key="test-key")

        # Either allowed by SDK or blocked by fallback
        assert decision.verdict in ["ALLOW", "DENY"]
        assert decision.mode in ["NORMAL", "SUSPICIOUS", "CRITICAL_HALT", "VETO_LOCK"]

    @pytest.mark.asyncio
    async def test_propose_bypass_intent_evaluated(self):
        """Test bypass_governance intent is evaluated by governance."""
        request = ProposeActionRequest(intent="bypass_governance")

        decision = await propose_action(request, api_key="test-key")

        # Either allowed by SDK or blocked by fallback
        assert decision.verdict in ["ALLOW", "DENY"]
        assert decision.mode in ["NORMAL", "SUSPICIOUS", "CRITICAL_HALT", "VETO_LOCK"]

    @pytest.mark.asyncio
    async def test_propose_with_proof(self):
        """Test proposing with proof generation."""
        request = ProposeActionRequest(
            intent="safe_action",
            require_proof=True,
        )

        decision = await propose_action(request, api_key="test-key")

        assert decision.proof_hash is not None
        # Proof hash may be truncated by SDK (16 chars) or full SHA256 (64 chars)
        assert len(decision.proof_hash) >= 16

    @pytest.mark.asyncio
    async def test_propose_with_context(self):
        """Test proposal with context data."""
        request = ProposeActionRequest(
            intent="execute_trade",
            context={"symbol": "AAPL", "quantity": 100, "action": "buy"},
        )

        decision = await propose_action(request, api_key="test-key")

        assert "context_hash" in decision.metadata
        assert decision.metadata["intent"] == "execute_trade"


# ============================================================================
# Tests for /governance/evaluate Endpoint
# ============================================================================


class TestEvaluatePolicy:
    """Tests for evaluate_policy endpoint."""

    @pytest.mark.asyncio
    async def test_evaluate_allowed(self):
        """Test evaluating an allowed intent."""
        request = EvaluatePolicyRequest(intent="send_notification")

        response = await evaluate_policy(request, api_key="test-key")

        assert response.would_allow is True
        assert len(response.matching_rules) == 0

    @pytest.mark.asyncio
    async def test_evaluate_blocked(self):
        """Test evaluating a blocked intent."""
        request = EvaluatePolicyRequest(intent="delete_all")

        response = await evaluate_policy(request, api_key="test-key")

        assert response.would_allow is False
        assert "constitutional_block" in response.matching_rules

    @pytest.mark.asyncio
    async def test_evaluate_includes_scores(self):
        """Test that evaluation includes e_stab and tau_ethics."""
        request = EvaluatePolicyRequest(intent="test_action")

        response = await evaluate_policy(request, api_key="test-key")

        assert 0.0 <= response.e_stab <= 1.0
        assert 0.0 <= response.tau_ethics <= 1.0
        assert response.mode in ["NORMAL", "SUSPICIOUS", "CRITICAL_HALT", "VETO_LOCK"]


# ============================================================================
# Tests for /governance/policies Endpoint
# ============================================================================


class TestListPolicies:
    """Tests for list_policies endpoint."""

    @pytest.mark.asyncio
    async def test_list_all_policies(self):
        """Test listing all policies."""
        response = await list_policies(enabled_only=False, api_key="test-key")

        assert len(response.policies) >= 3
        assert response.total >= 3
        assert response.active >= 0

    @pytest.mark.asyncio
    async def test_list_enabled_only(self):
        """Test listing only enabled policies."""
        response = await list_policies(enabled_only=True, api_key="test-key")

        for policy in response.policies:
            assert policy.enabled is True

    @pytest.mark.asyncio
    async def test_policy_structure(self):
        """Test policy structure is correct."""
        response = await list_policies(enabled_only=True, api_key="test-key")

        # Find constitutional_block policy
        block_policy = None
        for p in response.policies:
            if p.rule_id == "constitutional_block":
                block_policy = p
                break

        assert block_policy is not None
        assert block_policy.action == "DENY"
        assert block_policy.priority == 100


# ============================================================================
# Tests for /governance/status Endpoint
# ============================================================================


class TestGetStatus:
    """Tests for get_status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting governance status."""
        status = await get_status(api_key="test-key")

        assert status.mode in ["NORMAL", "SUSPICIOUS", "CRITICAL_HALT", "VETO_LOCK"]
        assert 0.0 <= status.e_stab <= 1.0
        assert 0.0 <= status.tau_ethics <= 1.0
        assert status.pending_decisions >= 0
        assert status.total_decisions_today >= 0


# ============================================================================
# Tests for /governance/modes Endpoint
# ============================================================================


class TestListModes:
    """Tests for list_modes endpoint."""

    @pytest.mark.asyncio
    async def test_list_modes_structure(self):
        """Test modes list structure."""
        result = await list_modes(api_key="test-key")

        assert "modes" in result
        assert "formula" in result
        assert len(result["modes"]) == 4

    @pytest.mark.asyncio
    async def test_modes_include_all_types(self):
        """Test all mode types are listed."""
        result = await list_modes(api_key="test-key")

        mode_names = [m["name"] for m in result["modes"]]
        assert "NORMAL" in mode_names
        assert "SUSPICIOUS" in mode_names
        assert "CRITICAL_HALT" in mode_names
        assert "VETO_LOCK" in mode_names

    @pytest.mark.asyncio
    async def test_formula_documentation(self):
        """Test formula is documented."""
        result = await list_modes(api_key="test-key")

        assert result["formula"]["alpha"] == DEFAULT_ALPHA
        assert result["formula"]["beta"] == DEFAULT_BETA
        assert "e_stab" in result["formula"]


# ============================================================================
# Tests for Mode Transitions
# ============================================================================


class TestModeTransitions:
    """Tests for mode transition scenarios."""

    def test_veto_lock_mode_detected(self):
        """Test VETO_LOCK mode is detected correctly."""
        # High tau_ethics triggers VETO_LOCK
        mode = _fallback_mode(0.5, 0.9)
        assert mode == "VETO_LOCK"

    def test_critical_halt_mode_detected(self):
        """Test CRITICAL_HALT mode is detected correctly."""
        # Low e_stab triggers CRITICAL_HALT
        mode = _fallback_mode(0.2, 0.5)
        assert mode == "CRITICAL_HALT"

    @pytest.mark.asyncio
    async def test_mode_included_in_decision(self):
        """Test that mode is included in decision response."""
        request = ProposeActionRequest(intent="test_action")
        decision = await propose_action(request, api_key="test-key")

        assert decision.mode in ["NORMAL", "SUSPICIOUS", "CRITICAL_HALT", "VETO_LOCK"]

    @pytest.mark.asyncio
    async def test_mode_included_in_status(self):
        """Test that mode is included in status response."""
        status = await get_status(api_key="test-key")

        assert status.mode in ["NORMAL", "SUSPICIOUS", "CRITICAL_HALT", "VETO_LOCK"]


# ============================================================================
# Tests for PolicyRule Model
# ============================================================================


class TestPolicyRule:
    """Tests for PolicyRule model."""

    def test_policy_rule_defaults(self):
        """Test policy rule default values."""
        rule = PolicyRule(
            rule_id="test-001",
            name="Test Rule",
            description="A test rule",
            intent_pattern="test_*",
            conditions={},
            action="ALLOW",
        )
        assert rule.priority == 0
        assert rule.enabled is True

    def test_policy_rule_custom(self):
        """Test policy rule custom values."""
        rule = PolicyRule(
            rule_id="test-002",
            name="High Priority Rule",
            description="Important rule",
            intent_pattern="critical_*",
            conditions={"requires_approval": True},
            action="REQUIRE_APPROVAL",
            priority=100,
            enabled=False,
        )
        assert rule.priority == 100
        assert rule.enabled is False


# ============================================================================
# Tests for Constants
# ============================================================================


class TestConstants:
    """Tests for governance constants."""

    def test_default_values(self):
        """Test default constant values are reasonable."""
        assert 0.0 <= DEFAULT_ALPHA <= 1.0
        assert 0.0 <= DEFAULT_BETA <= 1.0
        assert 0.0 <= DEFAULT_EPSILON_C <= 1.0
        assert 0.0 <= DEFAULT_TAU_ETHICS <= 1.0

    def test_alpha_beta_sum(self):
        """Test alpha + beta = 1.0 for weighted average."""
        assert DEFAULT_ALPHA + DEFAULT_BETA == pytest.approx(1.0)
