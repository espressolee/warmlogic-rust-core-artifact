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
from unittest.mock import MagicMock

from warm_logic.kernel.mesh.gossip import GossipAgent


class MockDHT:
    def __init__(self, node_id, network):
        self.node_id = node_id.encode() if isinstance(node_id, str) else node_id
        self.public_key = b"pk_" + self.node_id
        self.network = network
        self.routing = MagicMock()
        # Wire find_neighbors to network's view of topology
        self.routing.find_neighbors.side_effect = self._find_neighbors
        self.send = MagicMock(side_effect=self._send)

    def _find_neighbors(self, *args):
        return self.network.find_neighbors(self.node_id)

    def _send(self, contact, payload):
        self.network.send(self.node_id, contact, payload)


class MockNetwork:
    def __init__(self):
        self.agents = {}  # node_id -> GossipAgent
        self.partitions = []  # List of sets of node_ids. If empty, fully connected.

    def add_node(self, node_id, agent):
        self.agents[node_id] = agent

    def set_partition(self, groups):
        """
        groups: List[List[bytes]]
        e.g. [[b'A', b'B'], [b'C', b'D']]
        """
        self.partitions = [set(g) for g in groups]

    def heal(self):
        self.partitions = []

    def _is_reachable(self, src, dst):
        if not self.partitions:
            return True
        for group in self.partitions:
            if src in group and dst in group:
                return True
        return False

    def find_neighbors(self, requester_id):
        # Return mock contacts for reachable peers
        neighbors = []
        for nid, agent in self.agents.items():
            if nid == requester_id:
                continue
            if self._is_reachable(requester_id, nid):
                contact = MagicMock()
                contact.node_id = nid
                neighbors.append(contact)
        return neighbors

    def send(self, src, dst, payload):
        # dst is usually (ip, port) in real code, but here we can check targets
        # The GossipAgent implementation of dht.send might depend on implementation details.
        # Assuming send takes (payload, address_tuple) or similar.
        # But wait, GossipAgent uses dht.send(msg, (contact.ip, contact.port)).
        # We need to map address back to agent?
        # Or simpler: The MockDHT.send is called with target.
        # In our MockDHT, we can try to look up generic targets.

        # In test_gossip.py, dht.send is just mocked.
        # But GossipAgent calls: self.dht.send(msg, (c.address, c.port))

        # We need to map contact mocks to actual agents.
        # Let's verify how GossipAgent uses send.
        pass

    def distribute_gossip(self, src_id, payload):
        """Directly distribute to reachable peers."""
        import json

        # GossipAgent logic calls send() which we intercept here
        if isinstance(payload, bytes):
            data = json.loads(payload.decode("utf-8"))
        else:
            data = payload

        manifest_hash = data.get("manifest_hash")
        timestamp = data.get("timestamp")

        for nid, agent in self.agents.items():
            if nid == src_id:
                continue
            if self._is_reachable(src_id, nid):
                # Trigger receive
                agent.on_receive_manifest(src_id.decode(), manifest_hash, timestamp)


class TestMeshPartitionRecovery(unittest.IsolatedAsyncioTestCase):
    async def test_partition_convergence(self):
        network = MockNetwork()
        nodes = [b"A", b"B", b"C", b"D"]
        agents = {}

        for nid in nodes:
            dht = MockDHT(nid, network)

            # Decorate send to call network distribution
            def side_effect_send(contact, payload, _src=nid):  # capture closure
                network.distribute_gossip(_src, payload)

            dht.send.side_effect = side_effect_send

            # Create agent
            agent = GossipAgent(dht, local_manifest_hash="hash_v1")
            agents[nid] = agent
            network.add_node(nid, agent)
            await agent.start()

        # 1. Initial State: Fully Connected
        # Node A announces "hash_v2"
        agents[b"A"].set_local_hash("hash_v2")
        await agents[b"A"].announce_manifest()

        # Verify propagation
        # Since announce_manifest uses find_neighbors and sends to them
        # network.distribute_gossip logic simulates the arrival

        self.assertEqual(agents[b"B"]._received_manifests["A"].manifest_hash, "hash_v2")
        self.assertEqual(agents[b"C"]._received_manifests["A"].manifest_hash, "hash_v2")
        self.assertEqual(agents[b"D"]._received_manifests["A"].manifest_hash, "hash_v2")

        # 2. Partition: {A, B} | {C, D}
        network.set_partition([[b"A", b"B"], [b"C", b"D"]])

        # Node A updates to "hash_v3"
        agents[b"A"].set_local_hash("hash_v3")
        await agents[b"A"].announce_manifest()

        # B should see it
        self.assertEqual(agents[b"B"]._received_manifests["A"].manifest_hash, "hash_v3")
        # C and D should NOT (still v2)
        self.assertEqual(agents[b"C"]._received_manifests["A"].manifest_hash, "hash_v2")
        self.assertEqual(agents[b"D"]._received_manifests["A"].manifest_hash, "hash_v2")

        # Node C updates to "hash_C_divergent"
        agents[b"C"].set_local_hash("hash_C_divergent")
        await agents[b"C"].announce_manifest()

        # D should see it
        self.assertEqual(
            agents[b"D"]._received_manifests["C"].manifest_hash, "hash_C_divergent"
        )
        # A and B should NOT
        self.assertNotIn(
            "C", agents[b"A"]._received_manifests
        )  # Never heard from C yet? or old?
        # A received C in step 1? No, step 1 was A announcing. C never announced.

        # 3. Heal Partition
        network.heal()

        # Trigger gossip from A and C again to simulate periodic sync
        await agents[b"A"].announce_manifest()
        await agents[b"C"].announce_manifest()

        # Now everyone should converge (receive latest)
        self.assertEqual(agents[b"C"]._received_manifests["A"].manifest_hash, "hash_v3")
        self.assertEqual(agents[b"D"]._received_manifests["A"].manifest_hash, "hash_v3")

        self.assertEqual(
            agents[b"A"]._received_manifests["C"].manifest_hash, "hash_C_divergent"
        )
        self.assertEqual(
            agents[b"B"]._received_manifests["C"].manifest_hash, "hash_C_divergent"
        )

        for nid, agent in agents.items():
            await agent.stop()


if __name__ == "__main__":
    unittest.main()
