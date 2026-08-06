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
Anti-Entropy Protocol
Merkle tree based state reconciliation for partition recovery.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from warm_logic.kernel.mesh.dht import Contact, SovereignDHT

logger = logging.getLogger("AntiEntropy")

# Configuration
RECONCILE_INTERVAL = 30.0  # seconds between reconciliation attempts
SUBTREE_DEPTH = 4  # Merkle tree depth for efficient diff
MAX_SYNC_BATCH = 100  # max records per sync batch


@dataclass
class MerkleNode:
    """Node in the Merkle tree."""

    hash: str
    left: Optional["MerkleNode"] = None
    right: Optional["MerkleNode"] = None
    data_key: Optional[str] = None  # Only set for leaf nodes


@dataclass
class SyncStats:
    """Statistics for anti-entropy protocol."""

    reconciliations_attempted: int = 0
    reconciliations_successful: int = 0
    records_synced: int = 0
    conflicts_detected: int = 0
    last_reconcile_time: float = 0.0


class MerkleTree:
    """
    Simple Merkle tree for state fingerprinting.
    Enables efficient comparison of large datasets.
    """

    def __init__(self) -> None:
        self._leaves: List[Tuple[str, str]] = []  # (key, hash) pairs
        self._root: Optional[MerkleNode] = None

    def add_leaf(self, key: str, data_hash: str) -> None:
        """Add a leaf node (key-hash pair)."""
        self._leaves.append((key, data_hash))
        self._root = None  # Invalidate cached root

    def clear(self) -> None:
        """Clear all leaves."""
        self._leaves = []
        self._root = None

    def build(self) -> None:
        """Build the Merkle tree from leaves."""
        if not self._leaves:
            self._root = MerkleNode(hash=self._hash("EMPTY"))
            return

        # Sort leaves by key for deterministic ordering
        sorted_leaves = sorted(self._leaves, key=lambda x: x[0])

        # Create leaf nodes
        nodes = [MerkleNode(hash=h, data_key=k) for k, h in sorted_leaves]

        # Build tree bottom-up
        while len(nodes) > 1:
            next_level = []
            for i in range(0, len(nodes), 2):
                left = nodes[i]
                right = nodes[i + 1] if i + 1 < len(nodes) else left
                combined_hash = self._hash(left.hash + right.hash)
                parent = MerkleNode(hash=combined_hash, left=left, right=right)
                next_level.append(parent)
            nodes = next_level

        self._root = nodes[0] if nodes else None

    @property
    def root_hash(self) -> str:
        """Get root hash, building tree if needed."""
        if self._root is None:
            self.build()
        return self._root.hash if self._root else self._hash("EMPTY")

    def get_subtree_hashes(self, depth: int = SUBTREE_DEPTH) -> List[str]:
        """Get hashes at specified depth for efficient comparison."""
        if self._root is None:
            self.build()

        if not self._root:
            return []

        result: List[str] = []
        self._collect_at_depth(self._root, 0, depth, result)
        return result

    def _collect_at_depth(
        self, node: MerkleNode, current: int, target: int, result: List[str]
    ) -> None:
        """Collect node hashes at target depth."""
        if current == target or (node.left is None and node.right is None):
            result.append(node.hash)
            return

        if node.left:
            self._collect_at_depth(node.left, current + 1, target, result)
        if node.right and node.right != node.left:
            self._collect_at_depth(node.right, current + 1, target, result)

    @staticmethod
    def _hash(data: str) -> str:
        """Compute SHA256 hash."""
        return hashlib.sha256(data.encode()).hexdigest()


class AntiEntropyAgent:
    """
    Background agent for state reconciliation.
    Uses Merkle tree comparison to identify and sync divergent data.
    """

    def __init__(
        self,
        dht: "SovereignDHT",
        get_local_state: Callable[[], Dict[str, str]],
        apply_remote_record: Callable[[str, str], bool],
        interval: float = RECONCILE_INTERVAL,
    ) -> None:
        """
        Initialize anti-entropy agent.

        Args:
            dht: DHT instance for peer communication
            get_local_state: Callback returning {key: hash} of all local records
            apply_remote_record: Callback to apply a remote record (key, data) -> success
            interval: Seconds between reconciliation attempts
        """
        self.dht = dht
        self._get_local_state = get_local_state
        self._apply_remote_record = apply_remote_record
        self._interval = interval

        self._merkle = MerkleTree()
        self._stats = SyncStats()
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None

        # Callbacks
        self._on_sync_complete: Optional[Callable[[int], None]] = None
        self._on_conflict: Optional[Callable[[str, str, str], None]] = None

    def get_stats(self) -> Dict[str, Any]:
        """Return anti-entropy statistics."""
        return {
            "reconciliations_attempted": self._stats.reconciliations_attempted,
            "reconciliations_successful": self._stats.reconciliations_successful,
            "records_synced": self._stats.records_synced,
            "conflicts_detected": self._stats.conflicts_detected,
            "last_reconcile_time": self._stats.last_reconcile_time,
            "merkle_root": self._merkle.root_hash,
            "running": self._running,
        }

    async def start(self) -> None:
        """Start the anti-entropy agent."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._reconcile_loop())
        logger.info("[AntiEntropy] Agent started")

    async def stop(self) -> None:
        """Stop the anti-entropy agent."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[AntiEntropy] Agent stopped")

    def rebuild_merkle(self) -> str:
        """Rebuild Merkle tree from current state."""
        self._merkle.clear()

        state = self._get_local_state()
        for key, data_hash in state.items():
            self._merkle.add_leaf(key, data_hash)

        self._merkle.build()
        return self._merkle.root_hash

    async def _reconcile_loop(self) -> None:
        """Main reconciliation loop with adaptive backoff."""
        current_interval = self._interval
        max_interval = self._interval * 10
        min_interval = self._interval

        while self._running:
            try:
                await asyncio.sleep(current_interval)
                synced = await self.reconcile_with_random_peer()

                # Adaptive Logic
                if synced > 0:
                    # If we found work to do, stay active / reset backoff
                    current_interval = min_interval
                else:
                    # No work, or success but nothing to sync, gradually backoff?
                    # Actually, for "Blackout Recovery", backoff is usually for *failures*.
                    # But here, let's reset to min on success.
                    current_interval = min_interval

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AntiEntropy] Loop error: {e}")
                # Backoff on error
                current_interval = min(current_interval * 2, max_interval)
                logger.info(f"[AntiEntropy] Backing off to {current_interval}s")

    async def reconcile_with_random_peer(self) -> int:
        """
        Pick a random peer and attempt reconciliation.
        Returns number of records synchronized.
        """
        neighbors = self.dht.routing.find_neighbors(self.dht.node_id)
        if not neighbors:
            logger.debug("[AntiEntropy] No peers for reconciliation")
            return 0

        # Pick random peer
        import random

        peer = random.choice(neighbors)

        return await self.reconcile(peer)

    async def reconcile(self, peer: "Contact") -> int:
        """
        Reconcile state with a specific peer.
        Returns number of records synchronized.
        """
        self._stats.reconciliations_attempted += 1

        # Step 1: Rebuild local Merkle tree
        local_root = self.rebuild_merkle()

        # Step 2: Fetch peer's Merkle root
        peer_root = await self._fetch_merkle_root(peer)

        if peer_root == local_root:
            logger.debug(f"[AntiEntropy] Already synced with {peer.node_id.hex()[:8]}")
            self._stats.reconciliations_successful += 1
            return 0

        # Step 3: Compare subtrees to identify divergent branches
        local_subtrees = self._merkle.get_subtree_hashes()
        peer_subtrees = await self._fetch_subtree_hashes(peer)

        divergent_indices = self._find_divergent_subtrees(local_subtrees, peer_subtrees)

        if not divergent_indices:
            # Roots differ but subtrees match - rare edge case
            logger.warning("[AntiEntropy] Root mismatch but no divergent subtrees")
            return 0

        # Step 4: Fetch and apply missing records
        synced = 0
        for idx in divergent_indices:
            records = await self._fetch_subtree_records(peer, idx)
            for key, data in records:
                if self._apply_remote_record(key, data):
                    synced += 1
                else:
                    self._stats.conflicts_detected += 1
                    if self._on_conflict:
                        local_state = self._get_local_state()
                        self._on_conflict(key, local_state.get(key, ""), data)

        self._stats.records_synced += synced
        self._stats.last_reconcile_time = time.time()

        if synced > 0:
            self._stats.reconciliations_successful += 1
            logger.info(
                f"✅ [AntiEntropy] Synced {synced} records with {peer.node_id.hex()[:8]}"
            )
            if self._on_sync_complete:
                self._on_sync_complete(synced)

        return synced

    def _find_divergent_subtrees(
        self, local: List[str], remote: List[str]
    ) -> List[int]:
        """Find indices of divergent subtrees."""
        divergent = []
        max_len = max(len(local), len(remote))

        for i in range(max_len):
            local_hash = local[i] if i < len(local) else ""
            remote_hash = remote[i] if i < len(remote) else ""
            if local_hash != remote_hash:
                divergent.append(i)

        return divergent

    # ===== Network Operations (Real RPC Implementation) =====

    async def _fetch_merkle_root(self, peer: "Contact") -> str:
        """Fetch peer's Merkle root hash via RPC."""
        message = {
            "type": "MERKLE_ROOT_REQUEST",
            "sender_id": self.dht.node_id.hex(),
            "timestamp": time.time(),
        }

        try:
            response = await self.dht.rpc_call(peer, message, timeout=5.0)
            return response.get("merkle_root", "")
        except Exception as e:
            logger.warning(
                f"[AntiEntropy] Failed to fetch root from {peer.node_id.hex()[:8]}: {e}"
            )
            return ""

    async def _fetch_subtree_hashes(self, peer: "Contact") -> List[str]:
        """Fetch peer's subtree hashes via RPC."""
        message = {
            "type": "SUBTREE_HASHES_REQUEST",
            "sender_id": self.dht.node_id.hex(),
            "timestamp": time.time(),
        }

        try:
            response = await self.dht.rpc_call(peer, message, timeout=5.0)
            return response.get("subtree_hashes", [])
        except Exception as e:
            logger.warning(
                f"[AntiEntropy] Failed to fetch subtrees from {peer.node_id.hex()[:8]}: {e}"
            )
            return []

    async def _fetch_subtree_records(
        self, peer: "Contact", subtree_idx: int
    ) -> List[Tuple[str, str]]:
        """Fetch all records in a specific subtree via RPC."""
        message = {
            "type": "SUBTREE_RECORDS_REQUEST",
            "sender_id": self.dht.node_id.hex(),
            "subtree_idx": subtree_idx,
            "timestamp": time.time(),
        }

        try:
            response = await self.dht.rpc_call(peer, message, timeout=10.0)
            # Ensure we get a list of [key, hash] or [key, val] tuples
            # Depending on protocol design, we might need actual values here to apply them.
            # In `apply_remote_record`, we usually expect (key, value).
            # If the response contains (key, hash), we might need another fetch or included data.
            # Assuming SUBTREE_RECORDS_RESPONSE sends full data for sync.
            return response.get("records", [])
        except Exception as e:
            logger.warning(
                f"[AntiEntropy] Failed to fetch records {subtree_idx} from {peer.node_id.hex()[:8]}: {e}"
            )
            return []
