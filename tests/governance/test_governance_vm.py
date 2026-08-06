"""Tests for Governance VM."""

from __future__ import annotations

import pytest

from warm_logic_core.governance.gov_inputs import GovernanceInputs, CtAction, CtMode
from warm_logic_core.governance.gov_outputs import GovernanceOutputs, GovSAT, GovAction
from warm_logic_core.governance.gov_vm import eval_vm, eval_vm_from_dict, evaluate_batch


class TestGovernanceInputs:
    """Tests for GovernanceInputs."""

    def test_create_default_inputs(self):
        """Test creating default inputs."""
        inputs = GovernanceInputs.default()

        assert inputs.drift_alarm is False
        assert inputs.drift_regime == "stable"
        assert inputs.tests_failing is False
        assert inputs.security_violation is False
        assert inputs.ct_action == "noop"
        assert inputs.mode == "safe"
        assert inputs.rstar is None

    def test_create_inputs_with_values(self):
        """Test creating inputs with values."""
        inputs = GovernanceInputs(
            drift_alarm=True,
            drift_regime="volatile",
            tests_failing=False,
            security_violation=False,
            ct_action="train",
            mode="exploration",
            rstar=0.75,
        )

        assert inputs.drift_alarm is True
        assert inputs.drift_regime == "volatile"
        assert inputs.rstar == 0.75

    def test_inputs_to_dict(self):
        """Test serialization."""
        inputs = GovernanceInputs.default()
        data = inputs.to_dict()

        assert data["drift_alarm"] is False
        assert data["mode"] == "safe"

    def test_inputs_from_dict(self):
        """Test deserialization."""
        data = {
            "drift_alarm": True,
            "drift_regime": "volatile",
            "tests_failing": True,
            "security_violation": False,
            "ct_action": "eval",
            "mode": "validation",
            "rstar": 0.5,
        }

        inputs = GovernanceInputs.from_dict(data)

        assert inputs.drift_alarm is True
        assert inputs.tests_failing is True
        assert inputs.rstar == 0.5


class TestGovernanceOutputs:
    """Tests for GovernanceOutputs."""

    def test_create_outputs(self):
        """Test creating outputs."""
        outputs = GovernanceOutputs(
            govSAT="SatAllow",
            govAction="continue",
            reason="ok",
        )

        assert outputs.govSAT == "SatAllow"
        assert outputs.govAction == "continue"

    def test_allow_factory(self):
        """Test allow factory method."""
        outputs = GovernanceOutputs.allow("approved")

        assert outputs.govSAT == "SatAllow"
        assert outputs.govAction == "continue"
        assert outputs.is_allowed() is True
        assert outputs.is_blocked() is False

    def test_block_factory(self):
        """Test block factory method."""
        outputs = GovernanceOutputs.block("security_issue")

        assert outputs.govSAT == "SatBlock"
        assert outputs.govAction == "forbid"
        assert outputs.is_blocked() is True

    def test_review_factory(self):
        """Test review factory method."""
        outputs = GovernanceOutputs.review("needs_review")

        assert outputs.govSAT == "SatReview"
        assert outputs.govAction == "review"
        assert outputs.requires_review() is True

    def test_outputs_to_dict(self):
        """Test serialization."""
        outputs = GovernanceOutputs.allow("ok")
        data = outputs.to_dict()

        assert data["govSAT"] == "SatAllow"
        assert data["govAction"] == "continue"


class TestEvalVM:
    """Tests for eval_vm function."""

    def test_default_allows(self):
        """Test default inputs are allowed."""
        inputs = GovernanceInputs.default()
        outputs = eval_vm(inputs)

        assert outputs.govSAT == "SatAllow"
        assert outputs.govAction == "continue"
        assert "ok" in outputs.reason

    def test_security_violation_blocks(self):
        """Test security violation blocks."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=True,
            ct_action="noop",
            mode="safe",
        )

        outputs = eval_vm(inputs)

        assert outputs.govSAT == "SatBlock"
        assert outputs.govAction == "forbid"
        assert "security_violation" in outputs.reason

    def test_tests_failing_blocks(self):
        """Test failing tests blocks."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=True,
            security_violation=False,
            ct_action="noop",
            mode="safe",
        )

        outputs = eval_vm(inputs)

        assert outputs.govSAT == "SatBlock"
        assert outputs.govAction == "forbid"
        assert "tests_failing" in outputs.reason

    def test_drift_alarm_reviews(self):
        """Test drift alarm triggers review."""
        inputs = GovernanceInputs(
            drift_alarm=True,
            drift_regime="volatile",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
        )

        outputs = eval_vm(inputs)

        assert outputs.govSAT == "SatReview"
        assert outputs.govAction == "review"
        assert "drift_alarm" in outputs.reason

    def test_low_rstar_reviews(self):
        """Test low R* triggers review."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            rstar=0.2,  # Below 0.25 threshold
        )

        outputs = eval_vm(inputs)

        assert outputs.govSAT == "SatReview"
        assert outputs.govAction == "review"
        assert "low_rstar" in outputs.reason

    def test_penalty_upper_reviews(self):
        """Test high penalty upper bound triggers review."""
        inputs = GovernanceInputs(
            drift_alarm=False,
            drift_regime="stable",
            tests_failing=False,
            security_violation=False,
            ct_action="noop",
            mode="safe",
            extra={"penalty": (0.1, 0.6)},  # Upper > 0.5
        )

        outputs = eval_vm(inputs)

        assert outputs.govSAT == "SatReview"
        assert outputs.govAction == "review"
        assert "penalty_upper" in outputs.reason

    def test_multiple_issues(self):
        """Test multiple issues are recorded."""
        inputs = GovernanceInputs(
            drift_alarm=True,
            drift_regime="volatile",
            tests_failing=True,
            security_violation=True,
            ct_action="noop",
            mode="safe",
        )

        outputs = eval_vm(inputs)

        assert outputs.govSAT == "SatBlock"
        assert "security_violation" in outputs.reason
        assert "tests_failing" in outputs.reason

    def test_security_overrides_drift(self):
        """Test security violation overrides drift alarm."""
        inputs = GovernanceInputs(
            drift_alarm=True,
            drift_regime="volatile",
            tests_failing=False,
            security_violation=True,
            ct_action="noop",
            mode="safe",
        )

        outputs = eval_vm(inputs)

        assert outputs.govSAT == "SatBlock"  # Not just review


class TestEvalVMFromDict:
    """Tests for eval_vm_from_dict function."""

    def test_from_dict(self):
        """Test evaluation from dictionary."""
        inputs_dict = {
            "drift_alarm": False,
            "drift_regime": "stable",
            "tests_failing": False,
            "security_violation": False,
            "ct_action": "noop",
            "mode": "safe",
        }

        outputs = eval_vm_from_dict(inputs_dict)

        assert outputs["govSAT"] == "SatAllow"
        assert outputs["govAction"] == "continue"


class TestEvaluateBatch:
    """Tests for evaluate_batch function."""

    def test_batch_evaluation(self):
        """Test batch evaluation."""
        inputs_list = [
            GovernanceInputs.default(),
            GovernanceInputs(
                drift_alarm=True,
                drift_regime="volatile",
                tests_failing=False,
                security_violation=False,
                ct_action="noop",
                mode="safe",
            ),
            GovernanceInputs(
                drift_alarm=False,
                drift_regime="stable",
                tests_failing=True,
                security_violation=False,
                ct_action="noop",
                mode="safe",
            ),
        ]

        outputs = evaluate_batch(inputs_list)

        assert len(outputs) == 3
        assert outputs[0].govSAT == "SatAllow"
        assert outputs[1].govSAT == "SatReview"
        assert outputs[2].govSAT == "SatBlock"
