"""Tests for R* bridge."""

from __future__ import annotations

import pytest

from warm_logic_core.governance.gov_inputs import GovernanceInputs
from warm_logic_core.governance.gov_outputs import GovernanceOutputs
from warm_logic_core.governance.gov_rstar_bridge import (
    apply_rstar_overrides,
    calculate_rstar_modifier,
    get_rstar_status,
    RSTAR_BLOCK_THRESHOLD,
    RSTAR_REVIEW_THRESHOLD,
    RSTAR_SOFT_REVIEW_THRESHOLD,
    RSTAR_ALLOW_THRESHOLD,
)


class TestApplyRstarOverrides:
    """Tests for apply_rstar_overrides."""

    def test_no_rstar_passthrough(self):
        """Test no R* passes through."""
        inputs = GovernanceInputs.default()
        outputs = GovernanceOutputs.allow("ok")

        result = apply_rstar_overrides(inputs, outputs)

        assert result.govSAT == "SatAllow"

    def test_very_low_rstar_blocks(self):
        """Test R* < 0.2 blocks."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=0.15,
        )
        outputs = GovernanceOutputs.allow("ok")

        result = apply_rstar_overrides(inputs, outputs)

        assert result.govSAT == "SatBlock"
        assert result.govAction == "forbid"
        assert "rstar_block" in result.reason

    def test_low_rstar_reviews(self):
        """Test 0.2 <= R* < 0.3 reviews."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=0.25,
        )
        outputs = GovernanceOutputs.allow("ok")

        result = apply_rstar_overrides(inputs, outputs)

        assert result.govSAT == "SatReview"
        assert result.govAction == "review"
        assert "rstar_review" in result.reason

    def test_medium_rstar_soft_reviews(self):
        """Test 0.3 <= R* < 0.6 soft reviews."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=0.45,
        )
        outputs = GovernanceOutputs.allow("ok")

        result = apply_rstar_overrides(inputs, outputs)

        assert result.govSAT == "SatReview"
        assert "rstar_soft_review" in result.reason

    def test_high_rstar_allows_upgrade(self):
        """Test R* >= 0.8 can upgrade review to allow."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=0.85,
        )
        outputs = GovernanceOutputs.review("some_issue")

        result = apply_rstar_overrides(inputs, outputs)

        assert result.govSAT == "SatAllow"
        assert result.govAction == "continue"
        assert "rstar_allow" in result.reason

    def test_high_rstar_no_upgrade_if_blocked(self):
        """Test R* cannot upgrade blocked decisions."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=0.9,
        )
        outputs = GovernanceOutputs.block("critical_issue")

        result = apply_rstar_overrides(inputs, outputs)

        # Should remain blocked (no rstar_allow reason added)
        assert result.govSAT == "SatBlock"

    def test_rstar_at_boundary_block(self):
        """Test R* exactly at block boundary."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=RSTAR_BLOCK_THRESHOLD,  # 0.2
        )
        outputs = GovernanceOutputs.allow("ok")

        result = apply_rstar_overrides(inputs, outputs)

        # At boundary, should be review (not block)
        assert result.govSAT == "SatReview"

    def test_rstar_at_boundary_review(self):
        """Test R* exactly at review boundary."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=RSTAR_REVIEW_THRESHOLD,  # 0.3
        )
        outputs = GovernanceOutputs.allow("ok")

        result = apply_rstar_overrides(inputs, outputs)

        # At boundary, should be soft review
        assert result.govSAT == "SatReview"


class TestCalculateRstarModifier:
    """Tests for calculate_rstar_modifier."""

    def test_none_returns_neutral(self):
        """Test None returns neutral modifier."""
        modifier = calculate_rstar_modifier(None)
        assert modifier == 0.5

    def test_very_low_returns_zero(self):
        """Test very low R* returns 0."""
        modifier = calculate_rstar_modifier(0.1)
        assert modifier == 0.0

    def test_low_returns_minimal(self):
        """Test low R* returns minimal."""
        modifier = calculate_rstar_modifier(0.25)
        assert modifier == 0.25

    def test_medium_returns_moderate(self):
        """Test medium R* returns moderate."""
        modifier = calculate_rstar_modifier(0.45)
        assert modifier == 0.5

    def test_good_returns_significant(self):
        """Test good R* returns significant."""
        modifier = calculate_rstar_modifier(0.7)
        assert modifier == 0.75

    def test_excellent_returns_full(self):
        """Test excellent R* returns full."""
        modifier = calculate_rstar_modifier(0.9)
        assert modifier == 1.0


class TestGetRstarStatus:
    """Tests for get_rstar_status."""

    def test_none_returns_unknown(self):
        """Test None returns unknown."""
        status = get_rstar_status(None)
        assert status == "unknown"

    def test_critical_status(self):
        """Test critical status."""
        status = get_rstar_status(0.1)
        assert status == "critical"

    def test_warning_status(self):
        """Test warning status."""
        status = get_rstar_status(0.25)
        assert status == "warning"

    def test_caution_status(self):
        """Test caution status."""
        status = get_rstar_status(0.45)
        assert status == "caution"

    def test_good_status(self):
        """Test good status."""
        status = get_rstar_status(0.7)
        assert status == "good"

    def test_excellent_status(self):
        """Test excellent status."""
        status = get_rstar_status(0.9)
        assert status == "excellent"
