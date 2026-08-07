"""Verification test for Mesh Governance end-to-end."""

import asyncio
import json
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.kernel.consensus.p2p_transport import P2PTransport, SwarmMessage
from warm_logic.kernel.justice.gov_inputs import GovernanceInputs
from warm_logic.kernel.justice.gvm import eval_vm
from warm_logic.kernel.security.mesh import MeshConsensusManager
from warm_logic.kernel.security.witness import WitnessManager, WitnessSignature


async def test_mesh_governance_verification():
    print("Testing Era 3: Mesh Governance & Mode 3 GVM Verification...")

    # 1. Setup Mesh Components
    local_transport = P2PTransport(node_id="LOCAL_HOST")
    manager = WitnessManager(threshold=2)  # Set internal threshold to 2
    mesh_manager = MeshConsensusManager(local_transport, manager)

    # 2. Simulate Peer Responses
    # Peer nodes: NODE_A, NODE_B, NODE_C
    run_id = "MESH_RUN_001"
    target_hash = "9ca5ee0ec94c787e929329177e5fda6fec4eb9e19fe05834d68e1c589b32bd61"

    def simulate_peer_signature(peer_id: str):
        msg = SwarmMessage(
            "VETO_CHECK_RESPONSE",
            peer_id,
            {
                "run_id": run_id,
                "signature": f"SIG_{peer_id}_{run_id}",
                "timestamp": 12345,
            },
        )
        mesh_manager.handle_witness_response(msg)

    # 3. Request Consensus and Ingest Peer Signatures
    print("Requesting Mesh Consensus (Simulation)...")
    manager.create_bundle(run_id, target_hash)  # Initialize bundle in manager

    # Add 2 signatures (below threshold 3)
    simulate_peer_signature("NODE_A")
    simulate_peer_signature("NODE_B")

    bundle = manager.get_bundle(run_id)
    witness_bundle_json = json.dumps(bundle.to_dict())

    # Negative Case: Mode 3, Insufficient Peer Signatures (2 < 3) -> SatBlock
    print("Testing NEGATIVE case: Mode 3 + Insufficient Mesh Consensus (2/3)")
    inputs = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=3,
        witness_bundle=witness_bundle_json,
    )
    outputs = eval_vm(inputs)
    assert outputs.govSAT == "SatBlock", f"Expected SatBlock, got {outputs.govSAT}"
    assert outputs.reason == "mesh_consensus_insufficient", (
        f"Expected reason 'mesh_consensus_insufficient', got '{outputs.reason}'"
    )
    print("   PASS")

    # Positive Case: Mode 3, 3 Peer Signatures -> SatAllow
    print("Testing POSITIVE case: Mode 3 + Verified Mesh Consensus (3/3)")
    simulate_peer_signature("NODE_C")
    witness_bundle_json_v2 = json.dumps(bundle.to_dict())

    inputs_v2 = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=3,
        witness_bundle=witness_bundle_json_v2,
    )
    outputs_v2 = eval_vm(inputs_v2)
    assert outputs_v2.govSAT == "SatAllow", (
        f"Expected SatAllow, got {outputs_v2.govSAT} ({outputs_v2.reason})"
    )
    print("   PASS")

    print("\nALL MESH GOVERNANCE INVARIANTS SCENARIO OK (not verification).")


if __name__ == "__main__":
    asyncio.run(test_mesh_governance_verification())
