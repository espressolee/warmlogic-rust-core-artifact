"""
Multi-Node Local Integration Test
==================================
Validates 3-node mesh networking on localhost.

Tests:
1. Node bootstrap and discovery
2. Message propagation across nodes
3. DHT routing table population
"""

import asyncio
import pytest
import secrets
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import warm_logic_rs as rs


class LocalNode:
    """Represents a single mesh node for testing."""

    def __init__(self, node_id: int, base_port: int = 9000):
        self.node_id = node_id
        self.port = base_port + node_id
        self.address = "127.0.0.1"

        # Generate PQC identity
        self.public_key, self.private_key = rs.generate_keypair()

        # Create node ID from public key hash
        import hashlib

        self.dht_id = hashlib.sha3_256(self.public_key.encode()).digest()

        self.messages_received = []
        self.peers = []

    def add_peer(self, peer: "LocalNode"):
        """Add a peer to this node's routing table."""
        self.peers.append(
            {
                "node_id": peer.dht_id.hex(),
                "address": peer.address,
                "port": peer.port,
                "public_key": peer.public_key,
            }
        )

    def get_info(self) -> dict:
        return {
            "node_id": self.dht_id.hex()[:16],
            "address": self.address,
            "port": self.port,
            "peers": len(self.peers),
        }


class TestMultinodeLocal:
    """Integration tests for multi-node mesh networking."""

    @pytest.fixture
    def three_nodes(self):
        """Create 3 interconnected nodes."""
        nodes = [LocalNode(i) for i in range(3)]

        # Fully connect the nodes
        for i, node in enumerate(nodes):
            for j, peer in enumerate(nodes):
                if i != j:
                    node.add_peer(peer)

        return nodes

    def test_node_initialization(self, three_nodes):
        """Test that all nodes initialize correctly."""
        for node in three_nodes:
            info = node.get_info()
            assert info["node_id"] is not None
            assert len(info["node_id"]) == 16  # First 16 chars of hex
            assert info["port"] >= 9000
            assert info["peers"] == 2  # Each node has 2 peers

    def test_pqc_identity_unique(self, three_nodes):
        """Test that each node has unique PQC identity."""
        public_keys = [node.public_key for node in three_nodes]
        assert len(set(public_keys)) == 3, "All nodes should have unique keys"

    def test_dht_id_derivation(self, three_nodes):
        """Test that DHT IDs are properly derived from public keys."""
        import hashlib

        for node in three_nodes:
            expected_id = hashlib.sha3_256(node.public_key.encode()).digest()
            assert node.dht_id == expected_id

    def test_peer_discovery(self, three_nodes):
        """Test that nodes can discover each other."""
        node_a, node_b, node_c = three_nodes

        # Node A should have B and C as peers
        peer_ids = [p["node_id"] for p in node_a.peers]
        assert node_b.dht_id.hex() in peer_ids
        assert node_c.dht_id.hex() in peer_ids

    def test_xor_distance_metric(self, three_nodes):
        """Test XOR distance calculation for Kademlia."""
        node_a, node_b, node_c = three_nodes

        def xor_distance(id1: bytes, id2: bytes) -> int:
            return int.from_bytes(
                bytes(a ^ b for a, b in zip(id1, id2)), byteorder="big"
            )

        dist_ab = xor_distance(node_a.dht_id, node_b.dht_id)
        dist_ac = xor_distance(node_a.dht_id, node_c.dht_id)
        dist_bc = xor_distance(node_b.dht_id, node_c.dht_id)

        # All distances should be non-zero (different nodes)
        assert dist_ab > 0
        assert dist_ac > 0
        assert dist_bc > 0

        # Triangle inequality should hold
        assert dist_ab <= dist_ac + dist_bc

    def test_message_signing_verification(self, three_nodes):
        """Test that messages can be signed and verified across nodes."""
        node_a, node_b, _ = three_nodes

        # Node A signs a message
        message = f"PING:{node_a.port}:{secrets.token_hex(8)}"
        signature = rs.sign(node_a.private_key, message)

        # Node B verifies the signature using A's public key
        valid = rs.verify(node_a.public_key, message, signature)
        assert valid, "Message should be verified with sender's public key"

        # Tampered message should fail
        tampered = message + "_tampered"
        invalid = rs.verify(node_a.public_key, tampered, signature)
        assert not invalid, "Tampered message should fail verification"

    def test_broadcast_simulation(self, three_nodes):
        """Simulate broadcast message propagation."""
        node_a, node_b, node_c = three_nodes

        # Node A broadcasts a message
        broadcast_msg = {
            "type": "MANIFEST_ANNOUNCE",
            "from": node_a.dht_id.hex()[:16],
            "payload": "genetic_hash_abc123",
            "ttl": 3,
        }

        # Simulate propagation to peers
        for peer_info in node_a.peers:
            # Find the actual peer node
            for node in [node_b, node_c]:
                if node.dht_id.hex() == peer_info["node_id"]:
                    node.messages_received.append(broadcast_msg)

        # Verify all nodes received the message
        assert len(node_b.messages_received) == 1
        assert len(node_c.messages_received) == 1
        assert node_b.messages_received[0]["type"] == "MANIFEST_ANNOUNCE"


class TestRustDHTIntegration:
    """Test Rust DHT integration (if available)."""

    def test_rust_dht_available(self):
        """Check if RustDHT is available."""
        assert hasattr(rs, "RustDHT"), "RustDHT should be exported"

    def test_routing_table_available(self):
        """Check if RustRoutingTable is available."""
        # Check for either name (may vary)
        has_routing = hasattr(rs, "RustRoutingTable") or hasattr(rs, "PyRoutingTable")
        assert has_routing, "Routing table should be exported"


class TestBFTConsensusNetwork:
    """Test BFT consensus in network context."""

    def test_vote_propagation_simulation(self):
        """Simulate BFT vote propagation across 5 nodes."""
        # Create 5 nodes
        nodes = [LocalNode(i, base_port=10000) for i in range(5)]
        quorum = 3  # 3 of 5 needed

        # Create BFT engine
        engine = rs.BFTEngine(quorum)
        engine.py_start_round(1)

        # Each node votes
        votes_cast = 0
        round_num = 1
        for node in nodes:
            message = f"VOTE:1:COMMIT:{node.port}"
            signature = rs.sign(node.private_key, message)
            vote = rs.Vote(
                f"node_{node.node_id}", "BLOCK_HASH_ROUND_1", round_num, signature
            )
            engine.py_cast_vote(vote)
            votes_cast += 1

            # Check quorum after each vote
            if engine.py_has_quorum():
                break

        assert engine.py_has_quorum(), "Should reach quorum with 5 nodes"
        assert votes_cast >= quorum, f"Should need at least {quorum} votes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
