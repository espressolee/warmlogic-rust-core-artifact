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
from unittest.mock import AsyncMock, MagicMock

from warm_logic.kernel.mesh.anti_entropy import AntiEntropyAgent, MerkleTree


class TestMerkleTree(unittest.TestCase):
    def test_merkle_root_determinism(self):
        tree1 = MerkleTree()
        tree1.add_leaf("key1", "hashA")
        tree1.add_leaf("key2", "hashB")

        tree2 = MerkleTree()
        # Different insertion order
        tree2.add_leaf("key2", "hashB")
        tree2.add_leaf("key1", "hashA")

        self.assertEqual(tree1.root_hash, tree2.root_hash)

    def test_merkle_root_change(self):
        tree = MerkleTree()
        tree.add_leaf("key1", "hashA")
        root1 = tree.root_hash

        tree.add_leaf("key2", "hashB")
        root2 = tree.root_hash

        self.assertNotEqual(root1, root2)

    def test_subtree_hashes(self):
        tree = MerkleTree()
        # Add enough leaves to create depth
        for i in range(16):
            tree.add_leaf(f"key{i}", f"hash{i}")

        root = tree.root_hash
        subtrees = tree.get_subtree_hashes(depth=2)

        # At depth 2, binary tree (2^2) should have 4 nodes
        self.assertEqual(len(subtrees), 4)


class TestAntiEntropyAgent(unittest.IsolatedAsyncioTestCase):
    async def test_reconcile_match(self):
        dht = MagicMock()
        agent = AntiEntropyAgent(
            dht=dht,
            get_local_state=lambda: {"k1": "h1"},
            apply_remote_record=lambda k, d: True,
        )

        # Mock peer interaction
        peer = MagicMock()
        peer.node_id = b"peer1"

        # Mock fetch_merkle_root to return matching root
        agent.rebuild_merkle()
        matching_root = agent._merkle.root_hash
        agent._fetch_merkle_root = AsyncMock(return_value=matching_root)

        synced = await agent.reconcile(peer)

        self.assertEqual(synced, 0)
        self.assertEqual(agent._stats.reconciliations_successful, 1)

    async def test_reconcile_mismatch(self):
        dht = MagicMock()
        # Local has k1
        agent = AntiEntropyAgent(
            dht=dht,
            get_local_state=lambda: {"k1": "h1"},
            apply_remote_record=lambda k, d: True,
        )

        peer = MagicMock()

        # Peer has k1 and k2 -> different root
        # Mock peer methods
        agent._fetch_merkle_root = AsyncMock(return_value="different_root")

        # Subtrees differ at index 0 (simplified mock)
        agent._merkle.get_subtree_hashes = MagicMock(return_value=["local_sub"])
        agent._fetch_subtree_hashes = AsyncMock(return_value=["remote_sub"])

        # Fetching subtree returns missing k2
        agent._fetch_subtree_records = AsyncMock(return_value=[("k2", "data_k2")])

        apply_mock = MagicMock(return_value=True)
        agent._apply_remote_record = apply_mock

        synced = await agent.reconcile(peer)

        self.assertEqual(synced, 1)
        apply_mock.assert_called_with("k2", "data_k2")
