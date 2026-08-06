"""Verification test for Autonomy Mode 2 end-to-end."""

import json
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.kernel.justice.gov_inputs import GovernanceInputs
from warm_logic.kernel.justice.gvm import eval_vm


def test_autonomy_mode_2_verification():
    print("Testing Autonomy Mode 2 GVM Verification...")

    # 1. Setup Valid Witness Bundle
    with open("out/witness_auto_001.json", "r") as f:
        witness_bundle_json = f.read()

    # Positive Case: Mode 2, Valid Ethics, Valid Witness -> SatAllow
    print("Testing POSITIVE case: Mode 2 + Valid Witness")
    inputs = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=2,
        witness_bundle=witness_bundle_json,
    )
    outputs = eval_vm(inputs)
    assert outputs.govSAT == "SatAllow", (
        f"Expected SatAllow, got {outputs.govSAT} ({outputs.reason})"
    )
    print("   PASS")

    # Negative Case 1: Mode 2, Missing Witness -> SatBlock
    print("Testing NEGATIVE case: Mode 2 + Missing Witness")
    inputs = GovernanceInputs(
        mode="full", ethics_proof="VALID_PROOF", autonomy_mode=2, witness_bundle=None
    )
    outputs = eval_vm(inputs)
    assert outputs.govSAT == "SatBlock", f"Expected SatBlock, got {outputs.govSAT}"
    assert outputs.reason == "autonomy_witness_missing"
    print("   PASS")

    # Negative Case 2: Mode 2, Insufficient Witness (Threshold 3) -> SatBlock
    print("Testing NEGATIVE case: Mode 2 + Insufficient Witness (Threshold 3)")
    with open("out/witness_auto_001.json", "r") as f:
        data = json.load(f)
        data["threshold"] = 3
        insufficient_bundle = json.dumps(data)

    inputs = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=2,
        witness_bundle=insufficient_bundle,
    )
    outputs = eval_vm(inputs)
    assert outputs.govSAT == "SatBlock", f"Expected SatBlock, got {outputs.govSAT}"
    assert outputs.reason == "autonomy_witness_unsat"
    print("   PASS")

    print("\nALL AUTONOMY MODE 2 INVARIANTS VERIFIED.")


if __name__ == "__main__":
    test_autonomy_mode_2_verification()
