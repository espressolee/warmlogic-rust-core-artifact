import json
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.kernel.justice.gov_inputs import GovernanceInputs
from warm_logic.kernel.justice.gvm import eval_vm


def test_refusal_audit_spine():
    print("Testing Era 4: Sovereign Compliance Spine & Refusal Audit...")

    ledger_path = "ledger/refusal_spine.jsonl"
    if os.path.exists(ledger_path):
        os.remove(ledger_path)

    # Case: Autonomy Mode 3, Insufficient Peer Signatures -> SatBlock + Refusal Entry
    print("Simulating Refusal: Mode 3 + Insufficient Consensus")

    # Mock witness bundle with 2 signatures (threshold 1 to pass internal verification)
    # But mesh_threshold is 3 in GVM for Mode 3, so it should still fail mesh quorum.
    witness_bundle_json = json.dumps(
        {
            "run_id": "REPRO_REFUSAL_001",
            "target_hash": "abc",
            "threshold": 1,
            "signatures": [
                {"witness_id": "NODE_A", "signature": "sig1", "timestamp": 0},
                {"witness_id": "NODE_B", "signature": "sig2", "timestamp": 0},
            ],
        }
    )

    inputs = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=3,
        witness_bundle=witness_bundle_json,
        metadata={"run_id": "REPRO_REFUSAL_001"},
    )

    outputs = eval_vm(inputs)
    assert outputs.govSAT == "SatBlock"
    assert "mesh_consensus_insufficient" in outputs.reason
    print("   GVM Blocked successfully.")

    # Verify Ledger Entry
    print("Verifying Refusal Spine Ledger...")
    assert os.path.exists(ledger_path), "Refusal ledger not created!"

    with open(ledger_path, "r") as f:
        lines = f.readlines()
        assert len(lines) >= 1, "No entries in refusal ledger!"

        event = json.loads(lines[-1])
        print(f"   Latest Event ID: {event['event_id']}")
        assert event["category"] == "governance_block"
        assert "mesh_consensus_insufficient" in event["description"]
        assert event["context"]["run_id"] == "REPRO_REFUSAL_001"
        assert "sensitivity" in event

        # Verify Refusal Token
        assert "proof" in event, "Proof block missing from refusal event"
        token_json = event["proof"]["refusal_token"]
        token_data = json.loads(token_json)
        assert "token_id" in token_data
        assert "signature" in token_data
        print(f"   Refusal Token Found: {token_data['token_id']}")

    print("   Refusal audit entry verified.")
    print("\nSOVEREIGN COMPLIANCE SPINE SCENARIO OK (not verification).")


if __name__ == "__main__":
    test_refusal_audit_spine()
