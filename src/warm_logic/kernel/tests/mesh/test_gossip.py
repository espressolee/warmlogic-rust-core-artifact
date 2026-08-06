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
Tests for GossipProtocol
"""

import unittest
from unittest.mock import MagicMock

from warm_logic.kernel.mesh.gossip import GossipAgent, ManifestRecord


class TestGossipProtocol(unittest.IsolatedAsyncioTestCase):
    """Test cases for GossipAgent."""

    def setUp(self):
        """Set up mock DHT for testing."""
        self.mock_dht = MagicMock()
        self.mock_dht.node_id = bytes.fromhex("deadbeef" * 8)
        self.mock_dht.public_key = bytes.fromhex("cafebabe" * 8)
        self.mock_dht.routing.find_neighbors = MagicMock(return_value=[])
        self.mock_dht.send = MagicMock()

    async def test_gossip_agent_creation(self):
        """Test basic GossipAgent creation."""
        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")

        self.assertFalse(agent._running)
        self.assertEqual(agent.local_manifest_hash, "abc123")
        self.assertEqual(len(agent._received_manifests), 0)

    async def test_announce_manifest_no_neighbors(self):
        """Test announce with no neighbors returns 0."""
        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")

        count = await agent.announce_manifest()

        self.assertEqual(count, 0)
        self.mock_dht.send.assert_not_called()

    async def test_announce_manifest_with_neighbors(self):
        """Test announce broadcasts to all neighbors."""
        # Create mock neighbors
        mock_contact_1 = MagicMock()
        mock_contact_1.node_id = bytes.fromhex("11111111" * 8)
        mock_contact_2 = MagicMock()
        mock_contact_2.node_id = bytes.fromhex("22222222" * 8)

        self.mock_dht.routing.find_neighbors.return_value = [
            mock_contact_1,
            mock_contact_2,
        ]

        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")
        count = await agent.announce_manifest()

        self.assertEqual(count, 2)
        self.assertEqual(self.mock_dht.send.call_count, 2)
        self.assertEqual(agent._stats.announcements_sent, 1)

    async def test_on_receive_manifest_matching(self):
        """Test receiving a manifest that matches local."""
        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")

        result = agent.on_receive_manifest("sender123", "abc123", 12345.0)

        self.assertTrue(result)
        self.assertEqual(agent._stats.announcements_received, 1)
        self.assertEqual(agent._stats.verification_failures, 0)
        self.assertIn("sender123", agent._received_manifests)
        self.assertTrue(agent._received_manifests["sender123"].verified)

    async def test_on_receive_manifest_mismatch(self):
        """Test receiving a manifest that doesn't match local."""
        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")

        result = agent.on_receive_manifest("sender456", "xyz789", 12345.0)

        self.assertFalse(result)
        self.assertEqual(agent._stats.announcements_received, 1)
        self.assertEqual(agent._stats.verification_failures, 1)
        self.assertIn("sender456", agent._received_manifests)
        self.assertFalse(agent._received_manifests["sender456"].verified)

    async def test_get_stats(self):
        """Test stats reporting."""
        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")
        agent.on_receive_manifest("s1", "abc123", 1.0)
        agent.on_receive_manifest("s2", "xyz789", 2.0)

        stats = agent.get_stats()

        self.assertEqual(stats["announcements_received"], 2)
        self.assertEqual(stats["verification_failures"], 1)
        self.assertEqual(stats["peer_count"], 2)
        self.assertEqual(stats["unique_manifests_seen"], 2)

    async def test_check_consensus_full_match(self):
        """Test consensus check when all peers match."""
        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")
        agent.on_receive_manifest("peer1", "abc123", 1.0)
        agent.on_receive_manifest("peer2", "abc123", 2.0)

        result = agent.check_consensus()

        self.assertTrue(result["has_consensus"])
        self.assertEqual(result["majority_hash"], "abc123")
        self.assertEqual(len(result["deviants"]), 0)

    async def test_check_consensus_with_deviant(self):
        """Test consensus check with mismatch."""
        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")
        agent.on_receive_manifest("peer1", "abc123", 1.0)
        agent.on_receive_manifest("peer2", "abc123", 2.0)
        agent.on_receive_manifest("deviant", "xyz789", 3.0)

        result = agent.check_consensus()

        self.assertFalse(result["has_consensus"])
        self.assertEqual(result["majority_hash"], "abc123")
        self.assertEqual(len(result["deviants"]), 1)
        self.assertEqual(result["deviants"][0]["sender_id"], "deviant")

    async def test_start_and_stop(self):
        """Test gossip agent lifecycle."""
        agent = GossipAgent(self.mock_dht, local_manifest_hash="abc123")

        await agent.start()
        self.assertTrue(agent._running)
        self.assertIsNotNone(agent._task)

        await agent.stop()
        self.assertFalse(agent._running)


class TestManifestRecord(unittest.TestCase):
    """Test ManifestRecord dataclass."""

    def test_creation(self):
        record = ManifestRecord(
            sender_id="abc",
            manifest_hash="xyz",
            timestamp=12345.0,
            verified=True,
        )

        self.assertEqual(record.sender_id, "abc")
        self.assertEqual(record.manifest_hash, "xyz")
        self.assertEqual(record.timestamp, 12345.0)
        self.assertTrue(record.verified)

    def test_default_verified(self):
        record = ManifestRecord(
            sender_id="abc",
            manifest_hash="xyz",
            timestamp=12345.0,
        )

        self.assertFalse(record.verified)


if __name__ == "__main__":
    unittest.main()
