import asyncio
import os
import shutil
import time
from pathlib import Path

from warm_logic.kernel.consensus.raft_service import NodeState, RaftConsensusService


async def run_test():
    print("Starting Raft Reality Multi-Node Test")

    # Cleanup previous state
    out_dir = Path("out/raft_test")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Configure nodes
    # Node 1 will be the leader for this test
    # Node 2 will be the follower
    nodes_config = [
        {"id": "node1", "host": "127.0.0.1", "port": 5001},
        {"id": "node2", "host": "127.0.0.1", "port": 5002},
    ]

    # Node 1 Setup
    n1 = RaftConsensusService("node1", "127.0.0.1", 5001)
    n1.persistence.storage_path = out_dir
    n1.persistence.store.root_path = str(out_dir)
    n1.peers = [{"id": "node2", "host": "127.0.0.1", "port": 5002}]
    n1.role = NodeState.LEADER

    # Node 2 Setup
    n2 = RaftConsensusService("node2", "127.0.0.1", 5002)
    n2.persistence.storage_path = out_dir
    n2.persistence.store.root_path = str(out_dir)
    n2.peers = [{"id": "node1", "host": "127.0.0.1", "port": 5001}]

    # Start servers
    t1 = asyncio.create_task(n1.start())
    t2 = asyncio.create_task(n2.start())

    await asyncio.sleep(1)  # Wait for servers to bind

    # Test Replication
    print("Node 1 (Leader) replicating GOVDEC...")
    govdec = {"verdict": "ALLOW", "reason": "Test Reality Replication"}
    result = await n1.replicate_govdec(govdec)

    print(f"Result: {result}")

    # Verify Node 2 received it
    n2_log = n2.persistence.load_log()
    print(f"Node 2 Log: {n2_log[-1] if n2_log else 'Empty'}")

    success = result["replicated"] and len(n2_log) > 0

    if success:
        print("RAFT REALITY SCENARIO OK (not verification): P2P Replication Successful")
    else:
        print("RAFT REALITY FAILED: Replication Incomplete")

    # Cleanup
    t1.cancel()
    t2.cancel()

    return 0 if success else 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(run_test()))
