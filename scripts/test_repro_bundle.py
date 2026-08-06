"""Verification test for Sovereign Repro Bundles (Phase 4.3)."""

import glob
import json
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.kernel.justice.gov_inputs import GovernanceInputs
from warm_logic.kernel.justice.gvm import eval_vm
from warm_logic.kernel.ops.repro_bundler import repro_bundler


def test_repro_bundle_generation():
    print("Testing Era 4 Phase 4.3: Sovereign Repro Bundles...")

    # Cleanup previous bundles for clean verification
    existing_bundles = glob.glob(os.path.join(repro_bundler.bundle_dir, "*.wlid"))
    for b in existing_bundles:
        os.remove(b)

    # Trigger a Refusal (e.g., Mode 3 Insufficient Consensus)
    print("Triggering Refusal to generate bundle...")
    witness_bundle_json = json.dumps(
        {
            "run_id": "BUNDLE_TEST_001",
            "target_hash": "abc",
            "threshold": 1,
            "signatures": [
                {"witness_id": "NODE_A", "signature": "sig1", "timestamp": 0}
            ],
        }
    )

    inputs = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=3,
        witness_bundle=witness_bundle_json,
        metadata={"run_id": "BUNDLE_TEST_001"},
    )

    outputs = eval_vm(inputs)
    assert outputs.govSAT == "SatBlock"

    # Verify Bundle Creation
    bundles = glob.glob(os.path.join(repro_bundler.bundle_dir, "*.wlid"))
    assert len(bundles) >= 1, "❌ No repro bundle created after refusal!"

    bundle_path = bundles[0]
    print(f"Found Bundle: {bundle_path}")

    # Verify Bundle Content
    with open(bundle_path, "r") as f:
        content = json.load(f)

    print("   Verifying Bundle Integrity...")
    assert content["meta"]["format"] == "wlid_repro_v1"
    assert "integrity_hash" in content["meta"]

    evidence = content["evidence"]
    assert evidence["category"] == "governance_block"
    assert "mesh_consensus_insufficient" in evidence["description"]
    assert evidence["context"]["run_id"] == "BUNDLE_TEST_001"

    print("Bundle content valid.")
    print("\nSOVEREIGN REPRO BUNDLES VERIFIED.")


if __name__ == "__main__":
    test_repro_bundle_generation()
