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
Reputation-Based Mesh Sharding
Dynamically partitions the neural mesh based on node health, synaptic 
reliability, and historical performance (reputation).
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Set

from warm_logic.kernel.mesh.neural_mesh import NeuralMesh

logger = logging.getLogger("Sharding")


class ShardRank(Enum):
    """Mesh shard security levels."""

    CORE = "core"  # High-reputation, high-consensus
    PERIPHERY = "periphery"  # Trusted but lower performance
    SHADOW = "shadow"  # Low reputation, isolated for observation
    QUARANTINE = "quarantine"  # Untrusted or failing


@dataclass
class NodeReputation:
    """Historical reliability metrics for a node instance."""

    node_id: str
    uptime_score: float = 1.0
    latency_score: float = 1.0
    consensus_alignment: float = 1.0
    synaptic_reliability: float = 1.0
    last_updated: float = field(default_factory=time.time)

    @property
    def aggregate_score(self) -> float:
        """Calculate weighted reputation score [0.0, 1.0]."""
        return (
            self.uptime_score * 0.3
            + self.latency_score * 0.2
            + self.consensus_alignment * 0.3
            + self.synaptic_reliability * 0.2
        )


class ReputationShardManager:
    """
    Dynamically partitions the neural mesh.
    Isolates low-reputation nodes to protect global system stability.
    """

    def __init__(
        self,
        mesh: NeuralMesh,
        core_threshold: float = 0.85,
        shadow_threshold: float = 0.4,
    ):
        self.mesh = mesh
        self.core_threshold = core_threshold
        self.shadow_threshold = shadow_threshold
        self.node_reputations: Dict[str, NodeReputation] = {}
        self.shards: Dict[ShardRank, Set[str]] = {
            rank: set() for rank in ShardRank
        }

    def update_reputations(self) -> None:
        """Analyze mesh state and update reputation scores."""
        for node_id, node in self.mesh.nodes.items():
            if node_id not in self.node_reputations:
                self.node_reputations[node_id] = NodeReputation(node_id=node_id)
            
            rep = self.node_reputations[node_id]
            
            # Update reliability from mesh synapses
            rel_sum = 0.0
            synapse_count = len(node.synapses)
            if synapse_count > 0:
                for target_id in node.synapses:
                    synapse = node.synapses[target_id]
                    rel_sum += synapse.reliability
                rep.synaptic_reliability = rel_sum / synapse_count
            
            # Update latency score (inverse of latency)
            # In a real scenario, we'd pull from metrics
            
            rep.last_updated = time.time()
            self._reassign_shard(node_id, rep.aggregate_score)

    def _reassign_shard(self, node_id: str, score: float) -> None:
        """Move node between shards based on reputation score."""
        # Find current shard
        current_rank: Optional[ShardRank] = None
        for rank, nodes in self.shards.items():
            if node_id in nodes:
                current_rank = rank
                break
        
        # Determine new shard
        if score >= self.core_threshold:
            new_rank = ShardRank.CORE
        elif score >= self.shadow_threshold:
            new_rank = ShardRank.PERIPHERY
        elif score >= 0.1:
            new_rank = ShardRank.SHADOW
        else:
            new_rank = ShardRank.QUARANTINE

        if current_rank != new_rank:
            if current_rank:
                self.shards[current_rank].remove(node_id)
            self.shards[new_rank].add(node_id)
            logger.info(
                f"[Sharding] Node {node_id} reassigned: {current_rank} -> {new_rank} "
                f"(score: {score:.2f})"
            )

    def get_routing_whitelist(self, source_rank: ShardRank) -> Set[ShardRank]:
        """
        Define shard isolation policy.
        Core nodes should generally only route through other Core or Periphery nodes.
        """
        if source_rank == ShardRank.CORE:
            return {ShardRank.CORE, ShardRank.PERIPHERY}
        elif source_rank == ShardRank.PERIPHERY:
            return {ShardRank.CORE, ShardRank.PERIPHERY, ShardRank.SHADOW}
        elif source_rank == ShardRank.SHADOW:
            return {ShardRank.PERIPHERY, ShardRank.SHADOW}
        else:
            return set()

    def is_route_safe(self, source_id: str, target_id: str) -> bool:
        """Check if routing between two nodes is permitted by sharding policy."""
        source_rank = self.get_node_rank(source_id)
        target_rank = self.get_node_rank(target_id)
        
        if not source_rank or not target_rank:
            return False
            
        return target_rank in self.get_routing_whitelist(source_rank)

    def get_node_rank(self, node_id: str) -> Optional[ShardRank]:
        """Get the current shard rank of a node."""
        for rank, nodes in self.shards.items():
            if node_id in nodes:
                return rank
        return None
