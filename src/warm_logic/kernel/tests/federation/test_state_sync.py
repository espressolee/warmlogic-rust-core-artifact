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
Tests for State Synchronization module.
"""

import time
import unittest

from warm_logic.kernel.federation.state_sync import (
    ConflictResolution,
    RegionStateSynchronizer,
    StateMerkleTree,
    SyncableDecision,
    SyncBatch,
    VectorClock,
)


class TestVectorClock(unittest.TestCase):
    """Test VectorClock for causal ordering."""

    def test_increment(self):
        """Test clock increment."""
        vc = VectorClock()
        vc = vc.increment("node-1")
        self.assertEqual(vc.clocks["node-1"], 1)

        vc = vc.increment("node-1")
        self.assertEqual(vc.clocks["node-1"], 2)

    def test_merge(self):
        """Test clock merge (element-wise max)."""
        vc1 = VectorClock(clocks={"a": 2, "b": 1})
        vc2 = VectorClock(clocks={"a": 1, "b": 3, "c": 1})

        merged = vc1.merge(vc2)
        self.assertEqual(merged.clocks["a"], 2)
        self.assertEqual(merged.clocks["b"], 3)
        self.assertEqual(merged.clocks["c"], 1)

    def test_happens_before(self):
        """Test causal ordering."""
        vc1 = VectorClock(clocks={"a": 1, "b": 1})
        vc2 = VectorClock(clocks={"a": 2, "b": 2})

        self.assertTrue(vc1.happens_before(vc2))
        self.assertFalse(vc2.happens_before(vc1))

    def test_concurrent(self):
        """Test concurrent detection."""
        vc1 = VectorClock(clocks={"a": 2, "b": 1})
        vc2 = VectorClock(clocks={"a": 1, "b": 2})

        self.assertTrue(vc1.concurrent_with(vc2))
        self.assertTrue(vc2.concurrent_with(vc1))

    def test_pack_unpack(self):
        """Test serialization."""
        vc = VectorClock(clocks={"node-1": 5, "node-2": 3})
        packed = vc.pack()

        unpacked, consumed = VectorClock.unpack(packed)
        self.assertEqual(unpacked.clocks, vc.clocks)
        self.assertEqual(consumed, len(packed))


class TestSyncableDecision(unittest.TestCase):
    """Test SyncableDecision serialization."""

    def test_pack_unpack(self):
        """Test decision serialization."""
        vc = VectorClock(clocks={"node-1": 1})
        decision = SyncableDecision(
            decision_id="dec-123",
            region="us-east",
            timestamp=1700000000.0,
            vector_clock=vc,
            decision_hash="a" * 64,
            payload=b"test payload data",
            signature="b" * 128,
        )

        packed = decision.pack()
        unpacked = SyncableDecision.unpack(packed)

        self.assertEqual(unpacked.decision_id, decision.decision_id)
        self.assertEqual(unpacked.region, decision.region)
        self.assertEqual(unpacked.timestamp, decision.timestamp)
        self.assertEqual(unpacked.decision_hash, decision.decision_hash)
        self.assertEqual(unpacked.payload, decision.payload)


class TestStateMerkleTree(unittest.TestCase):
    """Test Merkle tree for state verification."""

    def test_add_decision(self):
        """Test adding decisions to tree."""
        tree = StateMerkleTree()
        tree.add_decision("dec-1", "hash1")
        tree.add_decision("dec-2", "hash2")

        self.assertIn("dec-1", tree.leaves)
        self.assertIn("dec-2", tree.leaves)

    def test_root_hash(self):
        """Test root hash computation."""
        tree = StateMerkleTree()
        tree.add_decision("dec-1", "hash1")

        root1 = tree.root_hash
        self.assertIsNotNone(root1)
        self.assertTrue(len(root1) > 0)

        # Adding another should change root
        tree.add_decision("dec-2", "hash2")
        root2 = tree.root_hash

        self.assertNotEqual(root1, root2)

    def test_same_content_same_hash(self):
        """Test deterministic hashing."""
        tree1 = StateMerkleTree()
        tree1.add_decision("dec-1", "hash1")
        tree1.add_decision("dec-2", "hash2")

        tree2 = StateMerkleTree()
        tree2.add_decision("dec-1", "hash1")
        tree2.add_decision("dec-2", "hash2")

        self.assertEqual(tree1.root_hash, tree2.root_hash)


class TestSyncBatch(unittest.TestCase):
    """Test SyncBatch serialization."""

    def test_pack_unpack(self):
        """Test batch serialization."""
        vc = VectorClock(clocks={"n": 1})
        decision = SyncableDecision(
            decision_id="dec-1",
            region="us-east",
            timestamp=time.time(),
            vector_clock=vc,
            decision_hash="a" * 64,
            payload=b"data",
        )

        batch = SyncBatch(
            batch_id="batch-123",
            source_region="us-east",
            target_region="eu-west",
            decisions=[decision],
            merkle_root="c" * 64,
        )

        packed = batch.pack()
        unpacked = SyncBatch.unpack(packed)

        self.assertEqual(unpacked.batch_id, batch.batch_id)
        self.assertEqual(unpacked.source_region, batch.source_region)
        self.assertEqual(unpacked.target_region, batch.target_region)
        self.assertEqual(len(unpacked.decisions), 1)


class TestRegionStateSynchronizer(unittest.TestCase):
    """Test cross-region state synchronization."""

    def test_add_local_decision(self):
        """Test adding local decisions."""
        sync = RegionStateSynchronizer("us-east", "node-1")

        decision = sync.add_local_decision("dec-1", b"payload data")

        self.assertEqual(decision.decision_id, "dec-1")
        self.assertEqual(decision.region, "us-east")
        self.assertIn("dec-1", sync.decisions)

    def test_create_sync_batch(self):
        """Test creating sync batch."""
        sync = RegionStateSynchronizer("us-east", "node-1")
        sync.add_local_decision("dec-1", b"data1")
        sync.add_local_decision("dec-2", b"data2")

        batch = sync.create_sync_batch("eu-west")

        self.assertEqual(batch.source_region, "us-east")
        self.assertEqual(batch.target_region, "eu-west")
        self.assertEqual(len(batch.decisions), 2)

    def test_receive_sync_batch_no_conflict(self):
        """Test receiving batch without conflicts."""
        sync1 = RegionStateSynchronizer("us-east", "node-1")
        sync2 = RegionStateSynchronizer("eu-west", "node-2")

        # Add decision to sync1
        sync1.add_local_decision("dec-1", b"data")

        # Create batch and send to sync2
        batch = sync1.create_sync_batch("eu-west")
        applied = sync2.receive_sync_batch(batch)

        self.assertEqual(len(applied), 1)
        self.assertIn("dec-1", sync2.decisions)

    def test_conflict_resolution_lww(self):
        """Test last-writer-wins conflict resolution."""
        sync1 = RegionStateSynchronizer(
            "us-east", "node-1", ConflictResolution.LAST_WRITER_WINS
        )
        sync2 = RegionStateSynchronizer(
            "eu-west", "node-2", ConflictResolution.LAST_WRITER_WINS
        )

        # Both regions add same decision ID with different data
        sync1.add_local_decision("dec-1", b"data-east")
        time.sleep(0.01)  # Ensure different timestamp
        sync2.add_local_decision("dec-1", b"data-west")  # Newer

        # Sync from west to east
        batch = sync2.create_sync_batch("us-east")
        applied = sync1.receive_sync_batch(batch)

        # West's decision should win (newer timestamp)
        self.assertEqual(len(applied), 1)
        self.assertEqual(sync1.decisions["dec-1"].payload, b"data-west")

    def test_vector_clock_ordering(self):
        """Test vector clock-based ordering."""
        sync1 = RegionStateSynchronizer("us-east", "node-1")
        sync2 = RegionStateSynchronizer("eu-west", "node-2")

        # Add decisions in sequence
        d1 = sync1.add_local_decision("dec-1", b"first")

        # Sync to node-2
        batch1 = sync1.create_sync_batch("eu-west")
        sync2.receive_sync_batch(batch1)

        # Node-2 adds dependent decision
        d2 = sync2.add_local_decision("dec-2", b"second")

        # d2's vector clock should be >= d1's
        self.assertFalse(d2.vector_clock.happens_before(d1.vector_clock))

    def test_get_sync_status(self):
        """Test status reporting."""
        sync = RegionStateSynchronizer("us-east", "node-1")
        sync.add_local_decision("dec-1", b"data")

        status = sync.get_sync_status()

        self.assertEqual(status["region"], "us-east")
        self.assertEqual(status["decision_count"], 1)
        self.assertIn("merkle_root", status)

    def test_conflict_callback(self):
        """Test conflict detection callback."""
        conflicts_detected = []

        def on_conflict(local, remote):
            conflicts_detected.append((local.decision_id, remote.decision_id))

        sync1 = RegionStateSynchronizer("us-east", "node-1")
        sync1.on_conflict_detected(on_conflict)

        # Create conflicting decisions
        sync1.add_local_decision("dec-1", b"local-data")

        # Simulate receiving conflicting remote decision
        remote_vc = VectorClock(clocks={"node-2": 1})  # Concurrent
        remote = SyncableDecision(
            decision_id="dec-1",
            region="eu-west",
            timestamp=time.time(),
            vector_clock=remote_vc,
            decision_hash="different" + "0" * 56,
            payload=b"remote-data",
        )

        batch = SyncBatch(
            batch_id="test",
            source_region="eu-west",
            target_region="us-east",
            decisions=[remote],
            merkle_root="0" * 64,
        )
        sync1.receive_sync_batch(batch)

        self.assertEqual(len(conflicts_detected), 1)


if __name__ == "__main__":
    unittest.main()
