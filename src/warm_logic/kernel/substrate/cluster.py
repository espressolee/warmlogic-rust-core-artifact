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
Cluster Orchestrator
Multi-node cluster management for WarmLogic deployments.

Provides:
- Node discovery and registration
- Peer health monitoring
- Consensus quorum management
- Network partition detection
- Automatic failover coordination
"""

import asyncio
import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ClusterOrchestrator")


class NodeRole(Enum):
    """Node roles in the cluster."""

    LEADER = "leader"
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    OBSERVER = "observer"  # Read-only node


class NodeState(Enum):
    """Node health states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    PARTITIONED = "partitioned"


@dataclass
class ClusterNode:
    """Information about a cluster node."""

    node_id: str
    address: str
    port: int
    role: NodeRole = NodeRole.FOLLOWER
    state: NodeState = NodeState.HEALTHY
    public_key: Optional[str] = None
    last_heartbeat: float = field(default_factory=time.time)
    joined_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_alive(self, timeout: float = 30.0) -> bool:
        """Check if node is considered alive based on heartbeat."""
        return (time.time() - self.last_heartbeat) < timeout


@dataclass
class ClusterConfig:
    """Cluster configuration."""

    cluster_id: str
    min_nodes: int = 1
    quorum_size: int = 1  # Auto-calculated: (n // 2) + 1
    heartbeat_interval: float = 5.0
    node_timeout: float = 30.0
    leader_election_timeout: float = 10.0
    partition_detection_threshold: int = 3  # Missed heartbeats before partition


class ClusterOrchestrator:
    """
    Manages multi-node cluster operations.
    Integrates with NetworkBridge for P2P communication.
    """

    def __init__(
        self,
        node_id: str,
        config: Optional[ClusterConfig] = None,
    ) -> None:
        self.node_id = node_id
        self.config = config or ClusterConfig(
            cluster_id=hashlib.sha256(b"warmlogic-cluster").hexdigest()[:16]
        )

        # Local node info
        self.local_node = ClusterNode(
            node_id=node_id,
            address=os.environ.get("CLUSTER_BIND_ADDR", "0.0.0.0"),
            port=int(os.environ.get("CLUSTER_BIND_PORT", "9000")),
            role=NodeRole.FOLLOWER,
        )

        # Cluster state
        self._nodes: Dict[str, ClusterNode] = {node_id: self.local_node}
        self._lock = threading.RLock()
        self._current_leader: Optional[str] = None
        self._term: int = 0  # Election term (Raft-like)

        # Network bridge integration
        self._network_bridge: Optional[Any] = None
        self._stitch_server: Optional[Any] = None

        # Background tasks
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._monitor_task: Optional[asyncio.Task[None]] = None

        # Callbacks
        self._on_leader_change: Optional[Callable[[str, Optional[str]], None]] = None
        self._on_node_join: Optional[Callable[[ClusterNode], None]] = None
        self._on_node_leave: Optional[Callable[[ClusterNode], None]] = None
        self._on_partition: Optional[Callable[[List[str]], None]] = None

    def connect_network(self, bridge: Any) -> None:
        """Connect to NetworkBridge for P2P communication."""
        self._network_bridge = bridge
        logger.info("[Cluster] NetworkBridge connected")

    def connect_stitch(self, stitch: Any) -> None:
        """Connect to StitchServer for HTTP/SSE."""
        self._stitch_server = stitch

        # Register cluster handlers
        from warm_logic.kernel.substrate.stitch_server import StitchServer

        StitchServer.register_handler("/cluster/join", self._handle_join_request)
        StitchServer.register_handler("/cluster/heartbeat", self._handle_heartbeat)
        StitchServer.register_handler("/cluster/vote", self._handle_vote_request)

        logger.info("[Cluster] StitchServer connected with handlers registered")

    async def start(self) -> None:
        """Start cluster operations."""
        if self._running:
            return

        self._running = True

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info(
            f"[Cluster] Started node {self.node_id[:8]}... "
            f"in cluster {self.config.cluster_id}"
        )

    async def stop(self) -> None:
        """Stop cluster operations."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()

        logger.info(f"[Cluster] Stopped node {self.node_id[:8]}...")

    def join_cluster(
        self,
        seed_address: str,
        seed_port: int,
    ) -> bool:
        """
        Join an existing cluster via a seed node.
        Sends join request and waits for acknowledgment.
        """
        join_request = {
            "type": "JOIN_REQUEST",
            "node_id": self.node_id,
            "address": self.local_node.address,
            "port": self.local_node.port,
            "public_key": self.local_node.public_key,
            "cluster_id": self.config.cluster_id,
        }

        if not seed_address or seed_port <= 0 or seed_port > 65535:
            logger.warning(
                f"[Cluster] Rejected invalid seed target: {seed_address}:{seed_port}"
            )
            return False

        if self._network_bridge:
            try:
                # Add seed as initial peer
                seed_id = hashlib.sha256(
                    f"{seed_address}:{seed_port}".encode()
                ).hexdigest()

                self._network_bridge.add_peer(seed_id, seed_address, seed_port)
                self._network_bridge.send_to_peer(seed_id, "CLUSTER_JOIN", join_request)

                logger.info(
                    f"[Cluster] Join request sent to seed {seed_address}:{seed_port}"
                )
                return True

            except Exception as e:
                logger.error(f"[Cluster] Join failed: {e}")
                return False

        return False

    def add_node(self, node: ClusterNode) -> bool:
        """Add a node to the cluster."""
        with self._lock:
            if node.node_id in self._nodes:
                # Update existing
                self._nodes[node.node_id].last_heartbeat = time.time()
                self._nodes[node.node_id].state = NodeState.HEALTHY
                return False

            self._nodes[node.node_id] = node
            self._update_quorum()

            logger.info(
                f"[Cluster] Node joined: {node.node_id[:8]}... "
                f"at {node.address}:{node.port}"
            )

            if self._on_node_join:
                self._on_node_join(node)

            # Broadcast to network
            if self._network_bridge:
                self._network_bridge.add_peer(
                    node.node_id, node.address, node.port, node.public_key
                )

            return True

    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the cluster."""
        with self._lock:
            if node_id not in self._nodes or node_id == self.node_id:
                return False

            node = self._nodes.pop(node_id)
            self._update_quorum()

            logger.info(f"[Cluster] Node left: {node_id[:8]}...")

            if self._on_node_leave:
                self._on_node_leave(node)

            # Update network bridge
            if self._network_bridge:
                self._network_bridge.remove_peer(node_id)

            # Check if we lost leader
            if self._current_leader == node_id:
                self._current_leader = None
                asyncio.create_task(self._start_election())

            return True

    def _update_quorum(self) -> None:
        """Update quorum size based on cluster size."""
        n = len(self._nodes)
        self.config.quorum_size = (n // 2) + 1
        logger.debug(f"[Cluster] Quorum updated: {self.config.quorum_size} of {n}")

    def get_nodes(self) -> List[ClusterNode]:
        """Get all cluster nodes."""
        with self._lock:
            return list(self._nodes.values())

    def get_healthy_nodes(self) -> List[ClusterNode]:
        """Get all healthy cluster nodes."""
        with self._lock:
            return [
                n for n in self._nodes.values() if n.is_alive(self.config.node_timeout)
            ]

    def get_leader(self) -> Optional[ClusterNode]:
        """Get current cluster leader."""
        with self._lock:
            if self._current_leader and self._current_leader in self._nodes:
                return self._nodes[self._current_leader]
            return None

    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self._current_leader == self.node_id

    def has_quorum(self) -> bool:
        """Check if cluster has quorum."""
        healthy = len(self.get_healthy_nodes())
        return healthy >= self.config.quorum_size

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to all nodes."""
        while self._running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)

                heartbeat = {
                    "type": "HEARTBEAT",
                    "node_id": self.node_id,
                    "term": self._term,
                    "leader_id": self._current_leader,
                    "timestamp": time.time(),
                }

                if self._network_bridge:
                    self._network_bridge.broadcast("CLUSTER_HEARTBEAT", heartbeat)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Cluster] Heartbeat error: {e}")

    async def _monitor_loop(self) -> None:
        """Monitor node health and detect partitions."""
        while self._running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval * 2)

                now = time.time()
                partitioned_nodes: List[str] = []

                with self._lock:
                    for node_id, node in self._nodes.items():
                        if node_id == self.node_id:
                            continue

                        elapsed = now - node.last_heartbeat

                        if elapsed > self.config.node_timeout:
                            if node.state != NodeState.UNREACHABLE:
                                node.state = NodeState.UNREACHABLE
                                logger.warning(
                                    f"[Cluster] Node unreachable: {node_id[:8]}..."
                                )
                                partitioned_nodes.append(node_id)

                        elif elapsed > self.config.heartbeat_interval * 2:
                            if node.state == NodeState.HEALTHY:
                                node.state = NodeState.DEGRADED
                                logger.info(
                                    f"[Cluster] Node degraded: {node_id[:8]}..."
                                )

                # Check for partition
                if partitioned_nodes and self._on_partition:
                    self._on_partition(partitioned_nodes)

                # Check quorum
                if not self.has_quorum():
                    logger.warning(
                        f"[Cluster] Quorum lost! "
                        f"Healthy: {len(self.get_healthy_nodes())}, "
                        f"Required: {self.config.quorum_size}"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Cluster] Monitor error: {e}")

    async def _start_election(self) -> None:
        """Start leader election (simplified Raft-like)."""
        if not self._running:
            return

        with self._lock:
            self._term += 1
            self.local_node.role = NodeRole.CANDIDATE
            votes_received = 1  # Vote for self

        logger.info(f"[Cluster] Starting election for term {self._term}")

        # Request votes from all nodes
        vote_request = {
            "type": "VOTE_REQUEST",
            "candidate_id": self.node_id,
            "term": self._term,
        }

        if self._network_bridge:
            self._network_bridge.broadcast("CLUSTER_VOTE", vote_request)

        # Wait for votes (simplified - in production use proper async voting)
        await asyncio.sleep(self.config.leader_election_timeout)

        # Check if we won (simplified - assumes we're the only candidate)
        with self._lock:
            if self.local_node.role == NodeRole.CANDIDATE:
                # For MVP: Become leader if no other leader exists
                if self._current_leader is None:
                    self._become_leader()

    def _become_leader(self) -> None:
        """Transition to leader role."""
        old_leader = self._current_leader
        self._current_leader = self.node_id
        self.local_node.role = NodeRole.LEADER

        logger.info(
            f"[Cluster] Node {self.node_id[:8]}... became leader (term {self._term})"
        )

        if self._on_leader_change:
            self._on_leader_change(self.node_id, old_leader)

        # Announce leadership
        if self._network_bridge:
            self._network_bridge.broadcast(
                "CLUSTER_LEADER",
                {
                    "leader_id": self.node_id,
                    "term": self._term,
                },
            )

    # --- HTTP Handlers for StitchServer ---

    def _handle_join_request(self, payload: Dict[str, Any]) -> None:
        """Handle cluster join request via StitchServer POST."""
        node_id = payload.get("node_id", "")
        address = payload.get("address", "")
        port = payload.get("port", 0)
        cluster_id = payload.get("cluster_id", "")

        if cluster_id != self.config.cluster_id:
            logger.warning(
                f"[Cluster] Rejected join from different cluster: {cluster_id}"
            )
            return

        new_node = ClusterNode(
            node_id=node_id,
            address=address,
            port=port,
            public_key=payload.get("public_key"),
        )

        self.add_node(new_node)

    def _handle_heartbeat(self, payload: Dict[str, Any]) -> None:
        """Handle heartbeat from peer."""
        node_id = payload.get("node_id", "")
        term = payload.get("term", 0)
        leader_id = payload.get("leader_id")

        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].last_heartbeat = time.time()
                self._nodes[node_id].state = NodeState.HEALTHY

            # Update leader if term is higher
            if term > self._term:
                self._term = term
                if leader_id and leader_id != self._current_leader:
                    old_leader = self._current_leader
                    self._current_leader = leader_id
                    self.local_node.role = NodeRole.FOLLOWER

                    if self._on_leader_change:
                        self._on_leader_change(leader_id, old_leader)

    def _handle_vote_request(self, payload: Dict[str, Any]) -> None:
        """Handle vote request from candidate."""
        candidate_id = payload.get("candidate_id", "")
        term = payload.get("term", 0)

        with self._lock:
            if term > self._term:
                # Grant vote (simplified - always vote for higher term)
                self._term = term
                vote_response = {
                    "type": "VOTE_RESPONSE",
                    "voter_id": self.node_id,
                    "candidate_id": candidate_id,
                    "term": term,
                    "vote_granted": True,
                }

                if self._network_bridge:
                    self._network_bridge.send_to_peer(
                        candidate_id, "CLUSTER_VOTE_RESPONSE", vote_response
                    )

    def get_status(self) -> Dict[str, Any]:
        """Get cluster status."""
        with self._lock:
            return {
                "cluster_id": self.config.cluster_id,
                "node_id": self.node_id,
                "role": self.local_node.role.value,
                "term": self._term,
                "leader_id": self._current_leader,
                "is_leader": self.is_leader(),
                "has_quorum": self.has_quorum(),
                "quorum_size": self.config.quorum_size,
                "total_nodes": len(self._nodes),
                "healthy_nodes": len(self.get_healthy_nodes()),
                "nodes": [
                    {
                        "id": n.node_id[:16],
                        "role": n.role.value,
                        "state": n.state.value,
                        "address": f"{n.address}:{n.port}",
                    }
                    for n in self._nodes.values()
                ],
            }
