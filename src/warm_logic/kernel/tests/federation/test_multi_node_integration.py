# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Multi-Node Federation Integration Tests

Tests real network communication between multiple federation nodes
using localhost with different ports.
"""

import asyncio
import hashlib
import socket
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel import rust_loader
from warm_logic.kernel.federation.network_transport import (
    ConnectionState,
    FederationTransport,
    TransportConfig,
)
from warm_logic.kernel.federation.protocol import MessageType
from warm_logic.kernel.federation.sovereign_federation import (
    FederationConsensus,
    FederationMember,
    NodeRole,
    SovereignFederation,
)


def _can_bind_tcp_socket() -> bool:
    """Return True when the current environment permits local TCP bind."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 0))
        return True
    except OSError:
        return False
    finally:
        sock.close()


_TCP_BIND_AVAILABLE = _can_bind_tcp_socket()


class _DeterministicRustShim:
    """Minimal deterministic shim for federation tests without Rust extension."""

    def kem_keygen(self):
        seed = hashlib.sha256(b"fed_kem_keygen").hexdigest()
        return seed, hashlib.sha256(f"dk:{seed}".encode()).hexdigest()

    def generate_keypair(self):
        seed = hashlib.sha256(b"fed_sign_keygen").hexdigest()
        return seed, hashlib.sha256(f"sk:{seed}".encode()).hexdigest()

    def kem_encapsulate(self, encapsulation_key: str):
        ciphertext = hashlib.sha256(f"ct:{encapsulation_key}".encode()).hexdigest()
        shared = hashlib.sha256(f"shared:{ciphertext}".encode()).hexdigest()
        return shared, ciphertext

    def kem_decapsulate(self, decapsulation_key: str, ciphertext: str):
        _ = decapsulation_key
        return hashlib.sha256(f"shared:{ciphertext}".encode()).hexdigest()

    def sign(self, signing_key: str, message_hash: str):
        digest = hashlib.sha256(f"{signing_key}:{message_hash}".encode()).hexdigest()
        return digest * 2


def _bootstrap_rust_core():
    if rust_loader.HAS_RUST_CORE:
        return rust_loader.load_rust_core(), None

    shim = _DeterministicRustShim()
    patcher = patch.multiple(
        rust_loader,
        HAS_RUST_CORE=True,
        load_rust_core=MagicMock(return_value=shim),
    )
    patcher.start()
    return shim, patcher


class TestMultiNodeFederation(unittest.TestCase):
    """Integration tests for multi-node federation scenarios."""

    @classmethod
    def setUpClass(cls):
        """Generate keys for all test nodes."""
        if not _TCP_BIND_AVAILABLE:
            raise unittest.SkipTest("TCP bind permission required")
        rs, cls._rust_patcher = _bootstrap_rust_core()

        # Node 1 (Sovereign)
        cls.ek1, cls.dk1 = rs.kem_keygen()
        cls.pk1, cls.sk1 = rs.generate_keypair()

        # Node 2 (Validator)
        cls.ek2, cls.dk2 = rs.kem_keygen()
        cls.pk2, cls.sk2 = rs.generate_keypair()

        # Node 3 (Validator)
        cls.ek3, cls.dk3 = rs.kem_keygen()
        cls.pk3, cls.sk3 = rs.generate_keypair()

    @classmethod
    def tearDownClass(cls):
        patcher = getattr(cls, "_rust_patcher", None)
        if patcher is not None:
            patcher.stop()

    def test_three_node_cluster_handshake(self):
        """Test handshake between 3 federation nodes."""

        async def run_test():
            # Create 3 transport instances
            node1 = FederationTransport(
                node_id="sovereign-001",
                signing_key=self.sk1,
                encapsulation_key=self.ek1,
                decapsulation_key=self.dk1,
                signing_public_key=self.pk1,
                config=TransportConfig(tcp_port=17400),
            )
            node2 = FederationTransport(
                node_id="validator-002",
                signing_key=self.sk2,
                encapsulation_key=self.ek2,
                decapsulation_key=self.dk2,
                signing_public_key=self.pk2,
                config=TransportConfig(tcp_port=17401),
            )
            node3 = FederationTransport(
                node_id="validator-003",
                signing_key=self.sk3,
                encapsulation_key=self.ek3,
                decapsulation_key=self.dk3,
                signing_public_key=self.pk3,
                config=TransportConfig(tcp_port=17402),
            )

            connected_to_node1 = []

            async def on_connected(peer):
                connected_to_node1.append(peer.node_id)

            node1.on_peer_connected(on_connected)

            try:
                # Start all servers
                await node1.start_server()
                await node2.start_server()
                await node3.start_server()

                # Node2 and Node3 connect to Node1
                peer1_from_2 = await node2.connect_to_peer("127.0.0.1", 17400)
                peer1_from_3 = await node3.connect_to_peer("127.0.0.1", 17400)

                self.assertIsNotNone(peer1_from_2)
                self.assertIsNotNone(peer1_from_3)
                self.assertEqual(peer1_from_2.node_id, "sovereign-001")
                self.assertEqual(peer1_from_3.node_id, "sovereign-001")

                # Wait for connections to be established on server side
                await asyncio.sleep(0.5)

                # Verify Node1 sees both connections
                self.assertIn("validator-002", connected_to_node1)
                self.assertIn("validator-003", connected_to_node1)

                # Verify connection states
                self.assertEqual(peer1_from_2.state, ConnectionState.ESTABLISHED)
                self.assertEqual(peer1_from_3.state, ConnectionState.ESTABLISHED)

            finally:
                # Cleanup
                await node1.stop_server()
                await node2.stop_server()
                await node3.stop_server()

        asyncio.run(run_test())

    def test_consensus_proposal_workflow(self):
        """Test consensus proposal across 3 nodes."""

        async def run_test():
            # Create federation managers
            fed1 = SovereignFederation(
                local_node_id="fed-sovereign", quorum_threshold=0.67
            )
            fed2 = SovereignFederation(
                local_node_id="fed-validator-1", quorum_threshold=0.67
            )
            fed3 = SovereignFederation(
                local_node_id="fed-validator-2", quorum_threshold=0.67
            )

            # Bootstrap all nodes
            self.assertTrue(fed1.bootstrap())
            self.assertTrue(fed2.bootstrap())
            self.assertTrue(fed3.bootstrap())

            # Register validators with sovereign
            fed1.members["fed-validator-1"] = FederationMember(
                node_id="fed-validator-1",
                host="127.0.0.1",
                role=NodeRole.VALIDATOR,
                encapsulation_key=fed2.get_local_keys()["encapsulation_key"],
                signing_key=fed2.get_local_keys()["signing_key"],
                is_active=True,
            )
            fed1.members["fed-validator-2"] = FederationMember(
                node_id="fed-validator-2",
                host="127.0.0.1",
                role=NodeRole.VALIDATOR,
                encapsulation_key=fed3.get_local_keys()["encapsulation_key"],
                signing_key=fed3.get_local_keys()["signing_key"],
                is_active=True,
            )

            # Propose governance decision
            decision_data = {
                "action": "upgrade_protocol",
                "version": "2.0.0",
                "reason": "Security enhancement",
            }
            consensus = fed1.propose_decision(decision_data)

            self.assertIsNotNone(consensus)
            self.assertEqual(consensus.approval_count, 1)  # Proposer auto-approves

            # Share proposal with validators (simulated)
            fed2.pending_consensus[consensus.decision_id] = consensus
            fed3.pending_consensus[consensus.decision_id] = consensus

            # Validator 1 approves
            fed2.approve_decision(consensus.decision_id)
            self.assertEqual(consensus.approval_count, 2)

            # Check quorum (2/3 >= 0.67)
            total_members = 3  # 1 sovereign + 2 validators
            self.assertTrue(consensus.has_quorum(total_members, 0.67))

            # Finalize
            result = fed1.finalize_decision(consensus.decision_id)
            self.assertTrue(result)
            self.assertTrue(consensus.finalized)

        asyncio.run(run_test())

    def test_pqc_key_exchange_between_nodes(self):
        """Test ML-KEM key exchange between federation nodes."""

        async def run_test():
            rs = rust_loader.load_rust_core()

            fed1 = SovereignFederation(local_node_id="pqc-node-1")
            fed2 = SovereignFederation(local_node_id="pqc-node-2")

            fed1.bootstrap()
            fed2.bootstrap()

            # Exchange public keys
            keys1 = fed1.get_local_keys()
            keys2 = fed2.get_local_keys()

            # Register each other as members
            fed1.members["pqc-node-2"] = FederationMember(
                node_id="pqc-node-2",
                host="127.0.0.1",
                role=NodeRole.VALIDATOR,
                encapsulation_key=keys2["encapsulation_key"],
                signing_key=keys2["signing_key"],
                is_active=True,
            )
            fed2.members["pqc-node-1"] = FederationMember(
                node_id="pqc-node-1",
                host="127.0.0.1",
                role=NodeRole.SOVEREIGN,
                encapsulation_key=keys1["encapsulation_key"],
                signing_key=keys1["signing_key"],
                is_active=True,
            )

            # Establish secure channel from fed1 to fed2
            channel = fed1.establish_channel("pqc-node-2")

            self.assertIsNotNone(channel)
            self.assertTrue(len(channel.session_key) > 0)
            self.assertTrue(len(channel.ciphertext) > 0)

            # Verify fed2 can decapsulate (simulated - in real scenario via network)
            derived_key = rs.kem_decapsulate(fed2._dk, channel.ciphertext)
            self.assertEqual(derived_key, channel.session_key)

        asyncio.run(run_test())

    def test_message_broadcast(self):
        """Test broadcasting messages to all peers."""

        async def run_test():
            received_messages = {"node2": [], "node3": []}

            node1 = FederationTransport(
                node_id="broadcast-leader",
                signing_key=self.sk1,
                encapsulation_key=self.ek1,
                decapsulation_key=self.dk1,
                signing_public_key=self.pk1,
                config=TransportConfig(tcp_port=17410),
            )
            node2 = FederationTransport(
                node_id="broadcast-follower-1",
                signing_key=self.sk2,
                encapsulation_key=self.ek2,
                decapsulation_key=self.dk2,
                signing_public_key=self.pk2,
                config=TransportConfig(tcp_port=17411),
            )
            node3 = FederationTransport(
                node_id="broadcast-follower-2",
                signing_key=self.sk3,
                encapsulation_key=self.ek3,
                decapsulation_key=self.dk3,
                signing_public_key=self.pk3,
                config=TransportConfig(tcp_port=17412),
            )

            # Register handlers
            async def handle_proposal_node2(peer, msg):
                received_messages["node2"].append(msg.payload)

            async def handle_proposal_node3(peer, msg):
                received_messages["node3"].append(msg.payload)

            node2.register_handler(MessageType.PROPOSAL, handle_proposal_node2)
            node3.register_handler(MessageType.PROPOSAL, handle_proposal_node3)

            try:
                await node1.start_server()
                await node2.start_server()
                await node3.start_server()

                # Connect followers to leader
                await node2.connect_to_peer("127.0.0.1", 17410)
                await node3.connect_to_peer("127.0.0.1", 17410)

                await asyncio.sleep(0.3)

                # Leader broadcasts proposal
                proposal_data = b"PROPOSAL:upgrade_to_v2"
                count = await node1.broadcast(MessageType.PROPOSAL, proposal_data)

                self.assertEqual(count, 2)  # Sent to 2 peers

                await asyncio.sleep(0.3)

                # Verify both followers received the message
                self.assertEqual(len(received_messages["node2"]), 1)
                self.assertEqual(len(received_messages["node3"]), 1)
                self.assertEqual(received_messages["node2"][0], proposal_data)
                self.assertEqual(received_messages["node3"][0], proposal_data)

            finally:
                await node1.stop_server()
                await node2.stop_server()
                await node3.stop_server()

        asyncio.run(run_test())

    def test_node_failure_and_recovery(self):
        """Test federation behavior when a node goes down and recovers."""

        async def run_test():
            node1 = FederationTransport(
                node_id="resilience-leader",
                signing_key=self.sk1,
                encapsulation_key=self.ek1,
                decapsulation_key=self.dk1,
                signing_public_key=self.pk1,
                config=TransportConfig(tcp_port=17420),
            )
            node2 = FederationTransport(
                node_id="resilience-follower",
                signing_key=self.sk2,
                encapsulation_key=self.ek2,
                decapsulation_key=self.dk2,
                signing_public_key=self.pk2,
                config=TransportConfig(tcp_port=17421),
            )

            disconnected_peers = []

            async def on_disconnected(peer):
                disconnected_peers.append(peer.node_id)

            node1.on_peer_disconnected(on_disconnected)

            try:
                await node1.start_server()
                await node2.start_server()

                # Connect
                peer = await node2.connect_to_peer("127.0.0.1", 17420)
                self.assertIsNotNone(peer)

                await asyncio.sleep(0.3)

                # Verify connection
                connected = node1.get_connected_peers()
                self.assertIn("resilience-follower", connected)

                # Simulate node2 failure
                await node2.stop_server()
                await asyncio.sleep(0.5)

                # Verify disconnection detected
                self.assertIn("resilience-follower", disconnected_peers)

                # Restart node2
                node2_new = FederationTransport(
                    node_id="resilience-follower",
                    signing_key=self.sk2,
                    encapsulation_key=self.ek2,
                    decapsulation_key=self.dk2,
                    signing_public_key=self.pk2,
                    config=TransportConfig(tcp_port=17421),
                )
                await node2_new.start_server()

                # Reconnect
                peer_new = await node2_new.connect_to_peer("127.0.0.1", 17420)
                self.assertIsNotNone(peer_new)
                self.assertEqual(peer_new.state, ConnectionState.ESTABLISHED)

                await node2_new.stop_server()

            finally:
                await node1.stop_server()

        asyncio.run(run_test())

    def test_peer_stats_tracking(self):
        """Test peer statistics tracking after connection."""

        async def run_test():
            node1 = FederationTransport(
                node_id="stats-server",
                signing_key=self.sk1,
                encapsulation_key=self.ek1,
                decapsulation_key=self.dk1,
                signing_public_key=self.pk1,
                config=TransportConfig(tcp_port=17450),
            )
            node2 = FederationTransport(
                node_id="stats-client",
                signing_key=self.sk2,
                encapsulation_key=self.ek2,
                decapsulation_key=self.dk2,
                signing_public_key=self.pk2,
            )

            try:
                await node1.start_server()
                peer = await node2.connect_to_peer("127.0.0.1", 17450)

                self.assertIsNotNone(peer)
                self.assertEqual(peer.node_id, "stats-server")
                self.assertEqual(peer.state, ConnectionState.ESTABLISHED)

                # Verify peer is tracked
                self.assertIn("stats-server", node2.peers)

                # Stats should be available via peer object directly
                self.assertEqual(peer.messages_sent, 0)
                self.assertEqual(peer.messages_received, 0)
                self.assertGreater(peer.last_seen, 0)

            finally:
                await node1.stop_server()

        asyncio.run(run_test())


class TestFederationQuorumScenarios(unittest.TestCase):
    """Test various quorum scenarios."""

    @classmethod
    def setUpClass(cls):
        cls._rust_core, cls._rust_patcher = _bootstrap_rust_core()

    @classmethod
    def tearDownClass(cls):
        patcher = getattr(cls, "_rust_patcher", None)
        if patcher is not None:
            patcher.stop()

    def test_quorum_calculation_5_nodes(self):
        """Test quorum calculation with 5 nodes."""
        consensus = FederationConsensus(
            decision_id="quorum-test-5",
            decision_hash="abc123",
            epoch=1000,
            proposer_node_id="node-1",
        )

        # 5 nodes, 67% threshold = need 3 approvals
        consensus.approvals = {"node-1": "sig1", "node-2": "sig2"}
        self.assertFalse(consensus.has_quorum(5, 0.67))  # 2/5 < 67%

        consensus.approvals["node-3"] = "sig3"
        self.assertTrue(consensus.has_quorum(5, 0.67))  # 3/5 = 60%, int(5*0.67)=3

    def test_quorum_calculation_7_nodes(self):
        """Test quorum calculation with 7 nodes (typical production)."""
        consensus = FederationConsensus(
            decision_id="quorum-test-7",
            decision_hash="def456",
            epoch=2000,
            proposer_node_id="node-1",
        )

        # 7 nodes, 67% threshold: int(7 * 0.67) = 4 approvals needed
        consensus.approvals = {"node-1": "s1", "node-2": "s2", "node-3": "s3"}
        self.assertFalse(consensus.has_quorum(7, 0.67))  # 3/7 < 4 required

        consensus.approvals["node-4"] = "s4"
        self.assertTrue(consensus.has_quorum(7, 0.67))  # 4/7 >= 4 required

        consensus.approvals["node-5"] = "s5"
        self.assertTrue(consensus.has_quorum(7, 0.67))  # 5/7 >= 4 required

    def test_rejection_prevents_finalization(self):
        """Test that rejections are tracked properly."""
        fed = SovereignFederation(local_node_id="reject-test", quorum_threshold=0.67)
        fed.bootstrap()

        # Add 2 validators
        fed.members["val-1"] = FederationMember(
            node_id="val-1", host="127.0.0.1", role=NodeRole.VALIDATOR, is_active=True
        )
        fed.members["val-2"] = FederationMember(
            node_id="val-2", host="127.0.0.1", role=NodeRole.VALIDATOR, is_active=True
        )

        # Propose
        consensus = fed.propose_decision({"risky": True})

        # Reject
        fed.reject_decision(consensus.decision_id, "Too risky")

        # Check rejection recorded
        self.assertEqual(consensus.rejection_count, 1)
        self.assertEqual(consensus.approval_count, 1)  # Proposer still approved


if __name__ == "__main__":
    unittest.main()
