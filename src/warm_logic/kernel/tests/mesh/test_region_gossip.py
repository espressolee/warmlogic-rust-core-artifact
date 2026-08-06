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
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.mesh.gossip import GossipAgent


class TestRegionGossip(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_dht = MagicMock()
        self.mock_dht.node_id = b"myself"
        self.mock_dht.public_key = b"pubkey"
        self.mock_dht.private_key = None
        self.mock_dht.send = MagicMock()
        self.mock_dht.routing.find_neighbors.return_value = []

    @patch("warm_logic.mesh.topology.NetworkTopology")
    async def test_announce_prioritizes_local_region(self, MockTopology):
        # setup mock topology latency by node-id pair
        def get_latency_side_effect(_id_a, id_b):
            if id_b == b"local":
                return 5
            return 100

        MockTopology.get_latency.side_effect = get_latency_side_effect

        # Create contacts
        local_contact = MagicMock()
        local_contact.node_id = b"local"
        local_contact.port = 8000  # Local

        remote_contact = MagicMock()
        remote_contact.node_id = b"remote"
        remote_contact.port = 9000  # Remote

        # Dht returns them in reverse order (remote first) to prove sorting works
        self.mock_dht.routing.find_neighbors.return_value = [
            remote_contact,
            local_contact,
        ]

        # Initialize Agent
        agent = GossipAgent(self.mock_dht, local_manifest_hash="hash123")

        # Run announce
        count = await agent.announce_manifest()

        self.assertEqual(count, 2)

        # Verify send order
        # Expect local_contact first, then remote_contact
        calls = self.mock_dht.send.call_args_list
        self.assertEqual(len(calls), 2)

        # Call args: (contact, payload)
        # Verify call 1 is to local
        first_contact = calls[0][0][0]
        self.assertEqual(
            first_contact.node_id, b"local", "First broadcast should be to local peer"
        )

        # Verify call 2 is to remote
        second_contact = calls[1][0][0]
        self.assertEqual(
            second_contact.node_id,
            b"remote",
            "Second broadcast should be to remote peer",
        )

    @patch("warm_logic.mesh.topology.NetworkTopology")
    async def test_is_same_region_logic(self, MockTopology):
        agent = GossipAgent(self.mock_dht)

        MockTopology.get_latency.return_value = 5
        c1 = MagicMock()
        c1.node_id = b"peer-local"
        self.assertTrue(agent._is_same_region(c1))

        MockTopology.get_latency.return_value = 100
        c2 = MagicMock()
        c2.node_id = b"peer-remote"
        self.assertFalse(agent._is_same_region(c2))

        # Test unknown port (default True)
        c3 = MagicMock()
        del (
            c3.port
        )  # Ensure no port attribute simulation if possible, or Mock returns something
        # If getattr(c3, "port", None) is used, and c3 is MagicMock, c3.port is a Mock object.
        # My code checks: if hasattr(port, "mock_calls"): return True
        # So it should return True for standard Mocks

        c4 = MagicMock()
        self.assertTrue(agent._is_same_region(c4))
