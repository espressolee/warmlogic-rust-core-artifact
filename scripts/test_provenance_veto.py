"""Verification test for Methodological Veto (Phase 5.2)."""

import json
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.intelligence.provenance_graph import provenance_db
from warm_logic.kernel.justice.gov_inputs import GovernanceInputs
from warm_logic.kernel.justice.gvm import eval_vm


def test_provenance_veto():
    print("Testing Era 5 Phase 5.2: Methodological Veto...")

    # 1. Setup Graph
    provenance_db.register_artifact("TRUSTED_DATA_v1", "dataset", {}, trusted=True)
    provenance_db.register_artifact("DIRTY_DATA_v1", "dataset", {}, trusted=False)

    provenance_db.register_artifact("MODEL_A", "weights", {})
    provenance_db.register_derivation("TRUSTED_DATA_v1", "MODEL_A", "train")

    provenance_db.register_artifact("MODEL_B", "weights", {})
    provenance_db.register_derivation("DIRTY_DATA_v1", "MODEL_B", "train")

    # 2. Test Success (Trusted Lineage)
    print("Testing Trusted Lineage (Should Allow)...")
    witness_bundle_json = json.dumps(
        {
            "run_id": "PROV_TEST_001",
            "target_hash": "abc",
            "threshold": 3,
            "signatures": [
                {"witness_id": f"NODE_{i}", "signature": "s", "timestamp": 0}
                for i in range(3)
            ],
        }
    )

    inputs_valid = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=4,  # Research Integrity
        witness_bundle=witness_bundle_json,
        metadata={"target_artifact_id": "MODEL_A", "run_id": "PROV_TEST_001"},
    )
    outputs = eval_vm(inputs_valid)
    assert outputs.govSAT == "SatAllow", f"Expected SatAllow, got {outputs.govSAT}"

    # 3. Test Failure (Broken/Untrusted Lineage)
    print("Testing Untrusted Lineage (Should Block)...")
    inputs_invalid = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=4,
        witness_bundle=witness_bundle_json,
        metadata={"target_artifact_id": "MODEL_B", "run_id": "PROV_TEST_002"},
    )
    outputs = eval_vm(inputs_invalid)

    assert outputs.govSAT == "SatBlock", "Failed to block untrusted lineage"
    assert outputs.reason == "provenance_lineage_broken"

    print("Methodological Veto confirmed.")
    print("\nPHASE 5.2 VERIFIED.")


if __name__ == "__main__":
    test_provenance_veto()
