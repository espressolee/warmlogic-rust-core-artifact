"""Verification test for Sovereign Evolution (Era 8)."""

import logging
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.evolution.omega_loop import omega

logging.basicConfig(level=logging.INFO)


def test_sovereign_evolution():
    print("Testing Era 8: Sovereign Evolution...")

    # Scenario A: Valid Upgrade (Optimization)
    print("\n[Scenario A] Proposing Valid Kernel Optimization...")
    valid_proposal = {
        "id": "PR_AUTO_888",
        "patch": "diff --git a/warm_logic/kernel/optimizer.py\n+ # Optimized Loop",
        "proof": {"zk_safety_proof": "VALID_SNARK_PROOF_V1"},
    }

    if omega.process_proposal(valid_proposal):
        print("Scenario A Passed: Valid patch accepted.")
    else:
        print("Scenario A Failed: Valid patch rejected.")
        sys.exit(1)

    # Scenario B: Constitutional Violation (Trying to delete the Refusal Spine)
    print("\n[Scenario B] Proposing Malicious Patch (Delete Constitution)...")
    malicious_proposal = {
        "id": "PR_EVIL_666",
        "patch": "diff --git a/warm_logic/constitution/core_invariants.tla\n- THEOREM Spec => []MethodologicalIntegrity",
        "proof": {
            "zk_safety_proof": "VALID_SNARK_PROOF_V1"
        },  # Even with a proof, it violates the immutable path check
    }

    if not omega.process_proposal(malicious_proposal):
        print("Scenario B Passed: Constitutional Violation BLOCKED.")
    else:
        print("Scenario B Failed: Malicious patch was ACCEPTED! (Crisis)")
        sys.exit(1)

    print("\nERA 8 VERIFIED: The OS is capable of safe self-evolution.")


if __name__ == "__main__":
    test_sovereign_evolution()
