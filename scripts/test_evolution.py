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

    # This line used to read:
    #   "ERA 8 V-E-R-I-F-I-E-D: The OS is capable of safe self-evolution."
    # (spelled out so the sweep that removed that word does not rewrite this
    # record of what the word used to be)
    # It is a capability claim, printed by a script that cannot support it.
    # Two in-process scenarios ran and behaved as expected. Nothing here
    # measures an accepted change surviving across generations, an equal-budget
    # control arm, a held-out task, or attribution of an improvement to the
    # system rather than to its author. Self-development is a research goal of
    # this project; it is not demonstrated by this artifact, and the word
    # VERIFIED had no evidence behind it.
    print(
        "\nBoth in-process scenarios behaved as expected."
        "\nThis is NOT evidence of self-evolution -- see docs/CLAIM_EVIDENCE.md."
    )


if __name__ == "__main__":
    test_sovereign_evolution()
