import asyncio
import os
import shutil
from pathlib import Path

from warm_logic.kernel.consensus.raft_service import NodeState, RaftConsensusService


async def run_test():
    print("Starting ZKP/PCC Reality Verification")

    # 1. Setup Environment
    os.environ["WARMLOGIC_HW_ROOT_SECRET"] = "SOVEREIGN_RESONANCE_2026"
    out_dir = Path("out/pcc_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Node 1 (Leader)
    n1 = RaftConsensusService("node1", "127.0.0.1", 6001)
    n1.persistence.store.root = out_dir
    n1.role = NodeState.LEADER

    # Node 2 (Follower)
    n2 = RaftConsensusService("node2", "127.0.0.1", 6002)
    n2.persistence.store.root = out_dir

    # Link nodes
    n1.peers = [{"id": "node2", "host": "127.0.0.1", "port": 6002}]

    # Start Node 2 server to receive RPCs
    # We'll use a mock P2P reception for this unit test
    print("Leader generating PCC-enforced GOVDEC...")
    govdec = {"verdict": "ALLOW", "reason": "PCC Reality Test"}

    # Replicate (This generates the proof)
    result = await n1.replicate_govdec(govdec)
    print(
        f"   ✅ Replication Status: {result['mode']} (Quorum: {result['quorum_achieved']})"
    )

    # Extract the entry and proof
    log = n1.persistence.load_log()
    entry = log[-1]
    proof = entry.get("zkp_proof")

    if proof:
        print(f"   ZKP Proof Generated: {proof['proof_hash'][:16]}...")
    else:
        print("   ZKP Proof MISSING!")
        return 1

    # 2. Verify Follower Side (PCC Enforcement)
    print("Follower verifying PCC proof chain...")

    # Simulate RPC reception on n2
    message = {"term": 1, "leader_id": "node1", "entries": [entry]}

    # Positive Test: Valid Proof
    resp = await n2._handle_append_entries(message)
    if resp.get("success"):
        print("   Follower accepted valid PCC proof.")
    else:
        print(f"   Follower rejected valid PCC proof: {resp.get('reason')}")
        return 1

    # Negative Test: Missing Proof
    print("Testing PCC Enforcement: Missing Proof rejection...")
    broken_entry = entry.copy()
    del broken_entry["zkp_proof"]
    message_broken = {"term": 1, "leader_id": "node1", "entries": [broken_entry]}

    resp_broken = await n2._handle_append_entries(message_broken)
    if not resp_broken.get("success") and resp_broken.get("reason") == "PCC_MISSING":
        print("   SUCCESS: Follower rejected entry with missing proof.")
    else:
        print("   FAILURE: Follower did not correctly reject missing proof.")
        return 1

    # Negative Test: Invalid Proof (Modified State)
    print("Testing PCC Enforcement: Invalid Proof Chain rejection...")
    tampered_entry = entry.copy()
    tampered_entry["data"] = {"verdict": "VETO", "reason": "TAMPERED"}
    message_tampered = {"term": 1, "leader_id": "node1", "entries": [tampered_entry]}

    resp_tampered = await n2._handle_append_entries(message_tampered)
    if (
        not resp_tampered.get("success")
        and resp_tampered.get("reason") == "PCC_DATA_MISMATCH"
    ):
        print("   SUCCESS: Follower rejected tampered entry (Data Mismatch).")
    else:
        print("   FAILURE: Follower did not catch tampered entry!")
        return 1

    print("\nZKP/PCC REALITY SCENARIO OK (not verification): Verifiable Proof Chains Enforced.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(run_test()))
