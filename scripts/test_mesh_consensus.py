"""Verification test for Sovereign Mesh (Era 16 - Ghost Mesh)."""

import asyncio
import logging
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.mesh.p2p_consensus import RealityPeer, SovereignMesh

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("MeshTest")


async def test_mesh_consensus():
    print("Testing Era 16: Ghost Mesh Async Consensus...")

    # 1. Setup Mesh (3 Nodes)
    nodes = []
    meshes = []

    for i in range(3):
        peer = RealityPeer(f"NODE_{i}", port=7000 + i)
        mesh = SovereignMesh()
        await mesh.boot(peer)
        nodes.append(peer)
        meshes.append(mesh)

    print(f"   Mesh established with {len(nodes)} active async nodes.")

    # 2. Simulate Event
    event = {
        "event_id": "REFUSAL_GHOST_123",
        "reason": "Ghost Mesh Verification",
        "timestamp": 1234567890,
    }

    # 3. Broadcast from NODE_0
    origin_mesh = meshes[0]
    print(f"   Node {nodes[0].node_id} broadcasting refusal via UDP...")
    await origin_mesh.broadcast_refusal(event)

    # 4. Wait for propagation
    print("   Waiting for resonance (500ms)...")
    await asyncio.sleep(0.5)

    # 5. Verify Consensus
    accepted_count = 0
    # The event hash is generated inside create_gossip_message
    msg = nodes[0].create_gossip_message(event)
    target_hash = msg["event_hash"]

    for i, peer in enumerate(nodes):
        if target_hash in peer.known_reality:
            accepted_count += 1
            print(f"   Node {peer.node_id} accepted reality.")

    # 6. Teardown
    for m in meshes:
        await m.close()

    ratio = accepted_count / len(nodes)
    if ratio == 1.0:
        print(f"Full Consensus Achieved (Ratio: {ratio:.2%}).")
        print("\nGHOST MESH VERIFIED.")
    else:
        print(f"Consensus Failed. Ratio: {ratio:.2%}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(test_mesh_consensus())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Test Failed: {e}")
        sys.exit(1)
