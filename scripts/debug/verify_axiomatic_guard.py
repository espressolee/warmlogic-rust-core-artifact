import logging
import os
import sys
from unittest.mock import MagicMock, patch

# Force the correct path
sys.path.append(os.getcwd())

from warm_logic.kernel.policy import (
    configure_guard_thresholds,
    enforce_critical_directive,
)
from warm_logic.kernel.substrate.axiomatic_guard import axiomatic_guard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyAxiomaticGuard")


def test_axiomatic_guard_execution():
    print("Starting Axiomatic Guard Verification...")

    # 1. Test configure_guard_thresholds (Protected by @axiomatic_guard)
    print("Testing Protected config update...")
    with patch(
        "warm_logic_rs.HardwareEntropy.verify_attestation", return_value=(True, "OK")
    ):
        with patch(
            "warm_logic.kernel.substrate.attestation.CrossNodeAttestation.challenge_tower",
            return_value=True,
        ):
            # Should pass
            configure_guard_thresholds(drift_max=0.7)
            print("Config update passed with valid attestation.")

    # 2. Test enforce_critical_directive
    print("Testing Critical Directive Enforcement...")
    action_called = False

    def mock_action():
        nonlocal action_called
        action_called = True

    with patch(
        "warm_logic_rs.HardwareEntropy.verify_attestation", return_value=(True, "OK")
    ):
        with patch(
            "warm_logic.kernel.substrate.attestation.CrossNodeAttestation.challenge_tower",
            return_value=True,
        ):
            res = enforce_critical_directive("DIR-001-TEST", mock_action)
            assert res.approved is True
            assert action_called is True
            print("Critical Directive enforced with valid attestation.")

    # 3. Test Failure Case (Hardware Mismatch)
    print("Testing Guard Block on Attestation Failure...")
    with patch(
        "warm_logic_rs.HardwareEntropy.verify_attestation",
        return_value=(False, "ID_MISMATCH"),
    ):
        try:
            configure_guard_thresholds(drift_max=0.6)
            print("Failure: Guard did not block execution on attestation error!")
            sys.exit(1)
        except RuntimeError as e:
            print(f"Guard correctly blocked execution: {e}")

    print("Axiomatic Guard Verification Successful!")


if __name__ == "__main__":
    try:
        test_axiomatic_guard_execution()
    except Exception as e:
        print(f"Verification Error: {e}")
        sys.exit(1)
