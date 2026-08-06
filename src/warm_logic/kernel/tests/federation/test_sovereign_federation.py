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
Sovereign Federation Tests

Tests the multi-node federation protocol with PQC key exchange
and consensus mechanisms.
"""

import unittest

from warm_logic.kernel import rust_loader
from warm_logic.kernel.federation import (
    FederationConsensus,
    FederationMember,
    FederationState,
    NodeRole,
    SecureChannel,
    SovereignFederation,
)


class TestFederationMember(unittest.TestCase):
    """Test FederationMember dataclass."""

    def test_member_creation(self):
        member = FederationMember(
            node_id="wl-test123",
            host="192.168.1.1",
            role=NodeRole.SOVEREIGN,
        )
        self.assertEqual(member.node_id, "wl-test123")
        self.assertEqual(member.role, NodeRole.SOVEREIGN)
        self.assertFalse(member.is_active)
        self.assertGreater(member.last_seen, 0)


class TestSecureChannel(unittest.TestCase):
    """Test SecureChannel dataclass."""

    def test_channel_creation(self):
        channel = SecureChannel(
            local_node_id="node-a",
            remote_node_id="node-b",
            session_key="abcd1234abcd1234" * 4,  # noqa: S105
            ciphertext="efgh5678" * 100,
        )
        self.assertTrue(channel.is_valid())
        self.assertEqual(channel.message_count, 0)

    def test_channel_expiry(self):
        channel = SecureChannel(
            local_node_id="node-a",
            remote_node_id="node-b",
            session_key="test_key_value",  # noqa: S105
            ciphertext="ct",
            established_at=0.0,  # Very old
        )
        self.assertFalse(channel.is_valid())


class TestFederationConsensus(unittest.TestCase):
    """Test FederationConsensus dataclass."""

    def test_consensus_creation(self):
        consensus = FederationConsensus(
            decision_id="fd-123",
            decision_hash="abc123",
            epoch=1000,
            proposer_node_id="node-a",
        )
        self.assertEqual(consensus.approval_count, 0)
        self.assertFalse(consensus.finalized)

    def test_consensus_quorum(self):
        consensus = FederationConsensus(
            decision_id="fd-123",
            decision_hash="abc123",
            epoch=1000,
            proposer_node_id="node-a",
            approvals={"node-a": "sig1", "node-b": "sig2", "node-c": "sig3"},
        )
        # 3/4: required = int(4 * 0.67) = 2, 3 >= 2 = True
        self.assertTrue(consensus.has_quorum(4, threshold=0.67))
        # 3/6: required = int(6 * 0.67) = 4, 3 >= 4 = False
        self.assertFalse(consensus.has_quorum(6, threshold=0.67))
        # 3/5: required = int(5 * 0.5) = 2, 3 >= 2 = True
        self.assertTrue(consensus.has_quorum(5, threshold=0.5))


class TestSovereignFederation(unittest.TestCase):
    """Test SovereignFederation manager."""

    @classmethod
    def setUpClass(cls):
        if not rust_loader.HAS_RUST_CORE:
            raise unittest.SkipTest("Rust core not available")

    def test_federation_initialization(self):
        fed = SovereignFederation(local_node_id="test-node-001")
        self.assertEqual(fed.state, FederationState.INITIALIZING)
        self.assertEqual(fed.local_node_id, "test-node-001")

    def test_federation_bootstrap(self):
        fed = SovereignFederation(local_node_id="test-node-002")
        result = fed.bootstrap()

        self.assertTrue(result)
        self.assertEqual(fed.state, FederationState.ACTIVE)

        # Check keys were generated
        keys = fed.get_local_keys()
        self.assertIn("encapsulation_key", keys)
        self.assertIn("signing_key", keys)
        self.assertTrue(len(keys["encapsulation_key"]) > 0)

    def test_propose_and_approve_decision(self):
        fed = SovereignFederation(local_node_id="test-node-003")
        fed.bootstrap()

        # Propose
        consensus = fed.propose_decision({"action": "upgrade", "version": "2.0"})
        self.assertIsNotNone(consensus)
        self.assertEqual(consensus.approval_count, 1)  # Proposer auto-approves

        # Finalize (only 1 member, so quorum reached)
        result = fed.finalize_decision(consensus.decision_id)
        self.assertTrue(result)
        self.assertTrue(consensus.finalized)

    def test_reject_decision(self):
        fed = SovereignFederation(local_node_id="test-node-004")
        fed.bootstrap()

        consensus = fed.propose_decision({"action": "risky"})
        fed.reject_decision(consensus.decision_id, "Too risky")

        # Now rejections should be recorded
        # Note: proposer auto-approves, so we have 1 approval + 1 rejection
        self.assertEqual(consensus.rejection_count, 1)

    def test_set_member_keys(self):
        fed = SovereignFederation(local_node_id="test-node-005")
        fed.bootstrap()

        # Add a mock member
        fed.members["remote-001"] = FederationMember(
            node_id="remote-001",
            host="192.168.1.100",
            role=NodeRole.VALIDATOR,
            is_active=True,
        )

        # Set keys
        result = fed.set_member_keys(
            "remote-001",
            encapsulation_key="ek_hex_data",
            signing_key="sk_hex_data",
        )
        self.assertTrue(result)
        self.assertEqual(fed.members["remote-001"].encapsulation_key, "ek_hex_data")

    def test_establish_channel(self):
        fed = SovereignFederation(local_node_id="test-node-006")
        fed.bootstrap()

        # Get another node's keys (simulate)
        ek, _ = fed.rs.kem_keygen()

        # Add member with encapsulation key
        fed.members["remote-002"] = FederationMember(
            node_id="remote-002",
            host="192.168.1.101",
            role=NodeRole.VALIDATOR,
            encapsulation_key=ek,
            is_active=True,
        )

        # Establish channel
        channel = fed.establish_channel("remote-002")
        self.assertIsNotNone(channel)
        self.assertEqual(channel.remote_node_id, "remote-002")
        self.assertTrue(len(channel.session_key) > 0)

    def test_get_state(self):
        fed = SovereignFederation(local_node_id="test-node-007")
        fed.bootstrap()

        state = fed.get_state()
        self.assertEqual(state["state"], "active")
        self.assertEqual(state["local_node_id"], "test-node-007")
        self.assertEqual(state["member_count"], 0)

    def test_get_active_members(self):
        fed = SovereignFederation(local_node_id="test-node-008")

        # Add mix of active and inactive members
        fed.members["active-1"] = FederationMember(
            node_id="active-1",
            host="192.168.1.1",
            role=NodeRole.SOVEREIGN,
            is_active=True,
        )
        fed.members["inactive-1"] = FederationMember(
            node_id="inactive-1",
            host="192.168.1.2",
            role=NodeRole.OBSERVER,
            is_active=False,
        )
        fed.members["active-2"] = FederationMember(
            node_id="active-2",
            host="192.168.1.3",
            role=NodeRole.VALIDATOR,
            is_active=True,
        )

        active = fed.get_active_members()
        self.assertEqual(len(active), 2)

    def test_multi_node_consensus(self):
        """Test consensus with multiple nodes."""
        fed = SovereignFederation(local_node_id="leader", quorum_threshold=0.5)
        fed.bootstrap()

        # Add two more members
        fed.members["node-2"] = FederationMember(
            node_id="node-2",
            host="192.168.1.2",
            role=NodeRole.VALIDATOR,
            is_active=True,
        )
        fed.members["node-3"] = FederationMember(
            node_id="node-3",
            host="192.168.1.3",
            role=NodeRole.VALIDATOR,
            is_active=True,
        )

        # Propose (leader auto-approves: 1/3)
        consensus = fed.propose_decision({"upgrade": True})
        self.assertFalse(consensus.has_quorum(3, 0.67))  # Need 2/3

        # Simulate another approval
        consensus.approvals["node-2"] = "sig_from_node_2"
        self.assertTrue(consensus.has_quorum(3, 0.67))  # 2/3 >= 0.67


if __name__ == "__main__":
    unittest.main()
