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
Cross-Region State Synchronization

Implements eventual consistency for multi-region federation:
- Decision replication with causal ordering
- Conflict detection and resolution (last-writer-wins + vector clocks)
- Merkle tree-based state verification
- Bandwidth-efficient delta sync
"""

import hashlib
import json
import logging
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("StateSync")


class SyncStatus(Enum):
    """Sync operation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolution(Enum):
    """Conflict resolution strategies."""

    LAST_WRITER_WINS = "lww"  # Timestamp-based
    VECTOR_CLOCK = "vc"  # Causal ordering
    MANUAL = "manual"  # Requires human intervention


@dataclass
class VectorClock:
    """Vector clock for causal ordering."""

    clocks: Dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str) -> "VectorClock":
        """Increment clock for a node."""
        new_clocks = dict(self.clocks)
        new_clocks[node_id] = new_clocks.get(node_id, 0) + 1
        return VectorClock(clocks=new_clocks)

    def merge(self, other: "VectorClock") -> "VectorClock":
        """Merge with another vector clock (element-wise max)."""
        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())
        new_clocks = {
            n: max(self.clocks.get(n, 0), other.clocks.get(n, 0)) for n in all_nodes
        }
        return VectorClock(clocks=new_clocks)

    def happens_before(self, other: "VectorClock") -> bool:
        """Check if this clock happens-before another (causal ordering)."""
        if not self.clocks:
            return bool(other.clocks)

        # This happens-before other iff:
        # - All entries in self are <= corresponding entries in other
        # - At least one entry is strictly <
        all_leq = all(
            self.clocks.get(n, 0) <= other.clocks.get(n, 0)
            for n in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        any_lt = any(
            self.clocks.get(n, 0) < other.clocks.get(n, 0)
            for n in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        return all_leq and any_lt

    def concurrent_with(self, other: "VectorClock") -> bool:
        """Check if two clocks are concurrent (conflict)."""
        return not self.happens_before(other) and not other.happens_before(self)

    def pack(self) -> bytes:
        """Serialize to bytes."""
        data = json.dumps(self.clocks).encode("utf-8")
        return struct.pack(">I", len(data)) + data

    @classmethod
    def unpack(cls, data: bytes) -> Tuple["VectorClock", int]:
        """Deserialize from bytes. Returns (clock, bytes_consumed)."""
        length = struct.unpack_from(">I", data, 0)[0]
        clocks = json.loads(data[4 : 4 + length].decode("utf-8"))
        return cls(clocks=clocks), 4 + length


@dataclass
class SyncableDecision:
    """A decision that can be synchronized across regions."""

    decision_id: str
    region: str
    timestamp: float
    vector_clock: VectorClock
    decision_hash: str
    payload: bytes
    signature: str = ""

    def pack(self) -> bytes:
        """Serialize for network transmission."""
        id_bytes = self.decision_id.encode("utf-8")
        region_bytes = self.region.encode("utf-8")
        hash_bytes = bytes.fromhex(self.decision_hash)
        sig_bytes = bytes.fromhex(self.signature) if self.signature else b""
        vc_bytes = self.vector_clock.pack()

        return struct.pack(
            f">H{len(id_bytes)}sH{len(region_bytes)}sd{len(vc_bytes)}s32sI{len(self.payload)}sH{len(sig_bytes)}s",
            len(id_bytes),
            id_bytes,
            len(region_bytes),
            region_bytes,
            self.timestamp,
            vc_bytes,
            hash_bytes,
            len(self.payload),
            self.payload,
            len(sig_bytes),
            sig_bytes,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "SyncableDecision":
        """Deserialize from bytes."""
        offset = 0

        id_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        decision_id = data[offset : offset + id_len].decode("utf-8")
        offset += id_len

        region_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        region = data[offset : offset + region_len].decode("utf-8")
        offset += region_len

        timestamp = struct.unpack_from(">d", data, offset)[0]
        offset += 8

        vector_clock, vc_len = VectorClock.unpack(data[offset:])
        offset += vc_len

        decision_hash = data[offset : offset + 32].hex()
        offset += 32

        payload_len = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        payload = data[offset : offset + payload_len]
        offset += payload_len

        sig_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        signature = data[offset : offset + sig_len].hex() if sig_len > 0 else ""

        return cls(
            decision_id=decision_id,
            region=region,
            timestamp=timestamp,
            vector_clock=vector_clock,
            decision_hash=decision_hash,
            payload=payload,
            signature=signature,
        )


@dataclass
class MerkleNode:
    """Node in a Merkle tree for state verification."""

    hash: str
    left: Optional["MerkleNode"] = None
    right: Optional["MerkleNode"] = None
    decision_id: Optional[str] = None  # Leaf nodes only


class StateMerkleTree:
    """Merkle tree for efficient state comparison."""

    def __init__(self):
        self.leaves: Dict[str, str] = {}  # decision_id -> hash
        self._root: Optional[MerkleNode] = None
        self._dirty = True

    def add_decision(self, decision_id: str, decision_hash: str) -> None:
        """Add a decision to the tree."""
        self.leaves[decision_id] = decision_hash
        self._dirty = True

    def remove_decision(self, decision_id: str) -> None:
        """Remove a decision from the tree."""
        if decision_id in self.leaves:
            del self.leaves[decision_id]
            self._dirty = True

    def _build_tree(self) -> Optional[MerkleNode]:
        """Build the Merkle tree from leaves."""
        if not self.leaves:
            return None

        # Create leaf nodes
        nodes = [
            MerkleNode(hash=h, decision_id=did)
            for did, h in sorted(self.leaves.items())
        ]

        # Build tree bottom-up
        while len(nodes) > 1:
            next_level = []
            for i in range(0, len(nodes), 2):
                left = nodes[i]
                right = nodes[i + 1] if i + 1 < len(nodes) else left

                combined = hashlib.sha3_256(
                    (left.hash + right.hash).encode()
                ).hexdigest()
                next_level.append(MerkleNode(hash=combined, left=left, right=right))

            nodes = next_level

        return nodes[0]

    @property
    def root_hash(self) -> str:
        """Get the root hash of the tree."""
        if self._dirty:
            self._root = self._build_tree()
            self._dirty = False
        return self._root.hash if self._root else ""

    def get_proof(self, decision_id: str) -> List[Tuple[str, bool]]:
        """Get Merkle proof for a decision. Returns list of (hash, is_right)."""
        if self._dirty:
            self._root = self._build_tree()
            self._dirty = False

        # Find path to leaf and collect sibling hashes
        proof = []
        # Implementation would traverse the tree
        # For now, return empty proof
        return proof

    def verify_proof(
        self, decision_id: str, decision_hash: str, proof: List[Tuple[str, bool]]
    ) -> bool:
        """Verify a Merkle proof."""
        current = decision_hash
        for sibling_hash, is_right in proof:
            if is_right:
                combined = current + sibling_hash
            else:
                combined = sibling_hash + current
            current = hashlib.sha3_256(combined.encode()).hexdigest()
        return current == self.root_hash


@dataclass
class SyncBatch:
    """A batch of decisions to synchronize."""

    batch_id: str
    source_region: str
    target_region: str
    decisions: List[SyncableDecision]
    merkle_root: str
    created_at: float = field(default_factory=time.time)
    status: SyncStatus = SyncStatus.PENDING

    def pack(self) -> bytes:
        """Serialize batch for transmission."""
        batch_id_bytes = self.batch_id.encode("utf-8")
        source_bytes = self.source_region.encode("utf-8")
        target_bytes = self.target_region.encode("utf-8")
        merkle_bytes = bytes.fromhex(self.merkle_root)

        # Pack decisions
        decision_bytes = b""
        for d in self.decisions:
            d_packed = d.pack()
            decision_bytes += struct.pack(">I", len(d_packed)) + d_packed

        return (
            struct.pack(
                f">H{len(batch_id_bytes)}sH{len(source_bytes)}sH{len(target_bytes)}s32sdI",
                len(batch_id_bytes),
                batch_id_bytes,
                len(source_bytes),
                source_bytes,
                len(target_bytes),
                target_bytes,
                merkle_bytes,
                self.created_at,
                len(self.decisions),
            )
            + decision_bytes
        )

    @classmethod
    def unpack(cls, data: bytes) -> "SyncBatch":
        """Deserialize from bytes."""
        offset = 0

        batch_id_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        batch_id = data[offset : offset + batch_id_len].decode("utf-8")
        offset += batch_id_len

        source_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        source_region = data[offset : offset + source_len].decode("utf-8")
        offset += source_len

        target_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        target_region = data[offset : offset + target_len].decode("utf-8")
        offset += target_len

        merkle_root = data[offset : offset + 32].hex()
        offset += 32

        created_at = struct.unpack_from(">d", data, offset)[0]
        offset += 8

        decision_count = struct.unpack_from(">I", data, offset)[0]
        offset += 4

        decisions = []
        for _ in range(decision_count):
            d_len = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            decision = SyncableDecision.unpack(data[offset : offset + d_len])
            decisions.append(decision)
            offset += d_len

        return cls(
            batch_id=batch_id,
            source_region=source_region,
            target_region=target_region,
            decisions=decisions,
            merkle_root=merkle_root,
            created_at=created_at,
        )


class RegionStateSynchronizer:
    """
    Cross-Region State Synchronizer

    Handles synchronization of governance decisions across geographic regions
    with eventual consistency guarantees.
    """

    def __init__(
        self,
        local_region: str,
        node_id: str,
        resolution_strategy: ConflictResolution = ConflictResolution.LAST_WRITER_WINS,
    ):
        self.local_region = local_region
        self.node_id = node_id
        self.resolution_strategy = resolution_strategy

        # Local state
        self.decisions: Dict[str, SyncableDecision] = {}
        self.merkle_tree = StateMerkleTree()
        self.vector_clock = VectorClock()

        # Sync state
        self.pending_batches: Dict[str, SyncBatch] = {}
        self.received_batches: Dict[str, SyncBatch] = {}
        self.conflicts: List[Tuple[SyncableDecision, SyncableDecision]] = []

        # Callbacks
        self._on_decision_applied: Optional[Callable[[SyncableDecision], None]] = None
        self._on_conflict_detected: Optional[
            Callable[[SyncableDecision, SyncableDecision], None]
        ] = None

        logger.info(
            f"[StateSync] Initialized for region {local_region}, node {node_id}"
        )

    def add_local_decision(
        self, decision_id: str, payload: bytes, signature: str = ""
    ) -> SyncableDecision:
        """Add a new local decision to be synchronized."""
        # Increment vector clock
        self.vector_clock = self.vector_clock.increment(self.node_id)

        # Compute hash
        decision_hash = hashlib.sha3_256(payload).hexdigest()

        decision = SyncableDecision(
            decision_id=decision_id,
            region=self.local_region,
            timestamp=time.time(),
            vector_clock=self.vector_clock,
            decision_hash=decision_hash,
            payload=payload,
            signature=signature,
        )

        self.decisions[decision_id] = decision
        self.merkle_tree.add_decision(decision_id, decision_hash)

        logger.info(f"[StateSync] Added local decision: {decision_id}")
        return decision

    def create_sync_batch(
        self, target_region: str, decision_ids: Optional[List[str]] = None
    ) -> SyncBatch:
        """Create a sync batch for a target region."""
        import os

        if decision_ids is None:
            # Sync all decisions
            decisions_to_sync = list(self.decisions.values())
        else:
            decisions_to_sync = [
                self.decisions[did] for did in decision_ids if did in self.decisions
            ]

        batch = SyncBatch(
            batch_id=f"sync-{os.urandom(8).hex()}",
            source_region=self.local_region,
            target_region=target_region,
            decisions=decisions_to_sync,
            merkle_root=self.merkle_tree.root_hash,
        )

        self.pending_batches[batch.batch_id] = batch
        logger.info(
            f"[StateSync] Created batch {batch.batch_id} with {len(decisions_to_sync)} decisions"
        )
        return batch

    def receive_sync_batch(self, batch: SyncBatch) -> List[SyncableDecision]:
        """
        Process a received sync batch.

        Returns list of decisions that were applied.
        """
        applied = []
        self.received_batches[batch.batch_id] = batch

        for remote_decision in batch.decisions:
            result = self._apply_remote_decision(remote_decision)
            if result:
                applied.append(remote_decision)

        batch.status = SyncStatus.COMPLETED
        logger.info(
            f"[StateSync] Processed batch {batch.batch_id}: {len(applied)}/{len(batch.decisions)} applied"
        )
        return applied

    def _apply_remote_decision(self, remote: SyncableDecision) -> bool:
        """Apply a remote decision with conflict resolution."""
        decision_id = remote.decision_id

        if decision_id not in self.decisions:
            # No conflict - just apply
            self.decisions[decision_id] = remote
            self.merkle_tree.add_decision(decision_id, remote.decision_hash)
            self.vector_clock = self.vector_clock.merge(remote.vector_clock)

            if self._on_decision_applied:
                self._on_decision_applied(remote)

            return True

        local = self.decisions[decision_id]

        # Check for conflict
        if local.decision_hash == remote.decision_hash:
            # Same decision, no conflict
            return True

        if remote.vector_clock.happens_before(local.vector_clock):
            # Remote is older, ignore
            logger.debug(f"[StateSync] Ignoring older decision: {decision_id}")
            return False

        if local.vector_clock.happens_before(remote.vector_clock):
            # Remote is newer, apply
            self.decisions[decision_id] = remote
            self.merkle_tree.add_decision(decision_id, remote.decision_hash)
            self.vector_clock = self.vector_clock.merge(remote.vector_clock)

            if self._on_decision_applied:
                self._on_decision_applied(remote)

            return True

        # Concurrent - need conflict resolution
        return self._resolve_conflict(local, remote)

    def _resolve_conflict(
        self, local: SyncableDecision, remote: SyncableDecision
    ) -> bool:
        """Resolve a conflict between concurrent decisions."""
        logger.warning(
            f"[StateSync] Conflict detected for {local.decision_id}: "
            f"local={local.region}@{local.timestamp:.0f}, "
            f"remote={remote.region}@{remote.timestamp:.0f}"
        )

        self.conflicts.append((local, remote))

        if self._on_conflict_detected:
            self._on_conflict_detected(local, remote)

        if self.resolution_strategy == ConflictResolution.LAST_WRITER_WINS:
            # Use timestamp, fallback to region name for determinism
            winner = remote if remote.timestamp > local.timestamp else local
            if remote.timestamp == local.timestamp:
                winner = remote if remote.region > local.region else local

            if winner == remote:
                self.decisions[local.decision_id] = remote
                self.merkle_tree.add_decision(local.decision_id, remote.decision_hash)
                return True
            return False

        elif self.resolution_strategy == ConflictResolution.VECTOR_CLOCK:
            # Already handled above - this is truly concurrent
            # Default to last-writer-wins
            return self._resolve_conflict_lww(local, remote)

        else:  # MANUAL
            # Mark for manual resolution
            return False

    def _resolve_conflict_lww(
        self, local: SyncableDecision, remote: SyncableDecision
    ) -> bool:
        """Last-writer-wins conflict resolution."""
        if remote.timestamp > local.timestamp:
            self.decisions[local.decision_id] = remote
            self.merkle_tree.add_decision(local.decision_id, remote.decision_hash)
            return True
        return False

    def get_missing_decisions(self, remote_merkle_root: str) -> List[str]:
        """
        Compare Merkle roots and identify missing decisions.

        Returns list of decision IDs that remote has but we don't.
        """
        if self.merkle_tree.root_hash == remote_merkle_root:
            return []  # States are identical

        # In a full implementation, would do tree traversal
        # For now, return empty (would need remote's tree structure)
        return []

    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status."""
        return {
            "region": self.local_region,
            "node_id": self.node_id,
            "decision_count": len(self.decisions),
            "merkle_root": self.merkle_tree.root_hash,
            "pending_batches": len(self.pending_batches),
            "received_batches": len(self.received_batches),
            "conflicts": len(self.conflicts),
            "vector_clock": self.vector_clock.clocks,
        }

    def on_decision_applied(self, callback: Callable[[SyncableDecision], None]) -> None:
        """Set callback for when a decision is applied."""
        self._on_decision_applied = callback

    def on_conflict_detected(
        self, callback: Callable[[SyncableDecision, SyncableDecision], None]
    ) -> None:
        """Set callback for conflict detection."""
        self._on_conflict_detected = callback
