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
Neural Mesh - Adaptive Intelligence Network

A self-organizing mesh network with neural-like properties:
- Adaptive routing based on latency and reliability
- Weight-based connection strength (synapse model)
- Distributed intelligence through collective computation
- Self-healing topology with automatic failover
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("NeuralMesh")


class SynapseState(Enum):
    """Connection states between neural nodes."""

    DORMANT = "dormant"  # No recent activity
    ACTIVE = "active"  # Currently in use
    POTENTIATED = "potentiated"  # Recently strengthened
    DEPRESSED = "depressed"  # Recently weakened
    PRUNED = "pruned"  # Marked for removal


@dataclass
class Synapse:
    """
    Neural connection between two mesh nodes.
    Implements Hebbian learning: "neurons that fire together wire together"
    """

    source_id: str
    target_id: str
    weight: float = 0.5  # Connection strength [0.0, 1.0]
    latency_ms: float = 100.0  # Average latency
    reliability: float = 1.0  # Success rate [0.0, 1.0]
    state: SynapseState = SynapseState.DORMANT
    last_activated: float = field(default_factory=time.time)
    activation_count: int = 0
    failure_count: int = 0

    def __post_init__(self) -> None:
        """Validate synapse parameters."""
        self.weight = max(0.0, min(1.0, self.weight))
        self.reliability = max(0.0, min(1.0, self.reliability))

    def activate(self, success: bool = True, latency: float = 0.0) -> None:
        """Record an activation event (message sent through this synapse)."""
        self.activation_count += 1
        self.last_activated = time.time()

        if success:
            # Strengthen on success (Hebbian learning)
            self._potentiate()
            # Update latency with exponential moving average
            alpha = 0.3
            self.latency_ms = (1 - alpha) * self.latency_ms + alpha * latency
        else:
            self.failure_count += 1
            self._depress()

        # Update reliability
        self.reliability = 1.0 - (self.failure_count / max(1, self.activation_count))

    def _potentiate(self) -> None:
        """Strengthen the synapse."""
        # Long-term potentiation (LTP) effect
        self.weight = min(1.0, self.weight + 0.05)
        self.state = SynapseState.POTENTIATED

    def _depress(self) -> None:
        """Weaken the synapse."""
        # Long-term depression (LTD) effect
        self.weight = max(0.0, self.weight - 0.1)
        self.state = SynapseState.DEPRESSED

    def should_prune(self, max_age_sec: float = 3600.0) -> bool:
        """Check if synapse should be pruned due to inactivity."""
        age = time.time() - self.last_activated
        return age > max_age_sec and self.weight < 0.1

    @property
    def fitness(self) -> float:
        """Calculate overall fitness score for routing decisions."""
        # Combine weight, reliability, and latency into fitness
        latency_factor = 1.0 / (1.0 + self.latency_ms / 100.0)
        return self.weight * self.reliability * latency_factor


@dataclass
class NeuralNode:
    """A node in the Neural Mesh network."""

    node_id: str
    address: str  # Network address (ip:port)
    capacity: float = 1.0  # Processing capacity [0.0, 1.0]
    load: float = 0.0  # Current load [0.0, 1.0]
    synapses: Dict[str, Synapse] = field(default_factory=dict)
    last_seen: float = field(default_factory=time.time)
    metadata: Dict[str, str] = field(default_factory=dict)

    def connect(self, target_id: str) -> Synapse:
        """Create or get synapse to target node."""
        if target_id not in self.synapses:
            self.synapses[target_id] = Synapse(
                source_id=self.node_id,
                target_id=target_id,
            )
        return self.synapses[target_id]

    def disconnect(self, target_id: str) -> None:
        """Remove synapse to target node."""
        if target_id in self.synapses:
            self.synapses[target_id].state = SynapseState.PRUNED
            del self.synapses[target_id]

    @property
    def available_capacity(self) -> float:
        """Get available processing capacity."""
        return max(0.0, self.capacity - self.load)


class NeuralMesh:
    """
    Self-organizing Neural Mesh Network

    Implements a neural-like distributed network with:
    - Adaptive routing based on synapse fitness
    - Hebbian learning for connection optimization
    - Automatic topology healing
    - Collective intelligence support
    """

    def __init__(
        self,
        local_node_id: str,
        local_address: str = "127.0.0.1:17500",
        learning_rate: float = 0.1,
        prune_interval_sec: float = 300.0,
    ):
        self.local_node_id = local_node_id
        self.learning_rate = learning_rate
        self.prune_interval_sec = prune_interval_sec

        # Create local node
        self.local_node = NeuralNode(
            node_id=local_node_id,
            address=local_address,
        )

        # Network topology
        self.nodes: Dict[str, NeuralNode] = {local_node_id: self.local_node}
        self.active_routes: Dict[str, List[str]] = {}  # dest -> path

        # Callbacks
        self._on_node_joined: Optional[Callable[[NeuralNode], None]] = None
        self._on_node_left: Optional[Callable[[str], None]] = None
        self._on_route_updated: Optional[Callable[[str, List[str]], None]] = None

        # Metrics
        self._total_messages = 0
        self._successful_routes = 0
        self._last_prune = time.time()

        logger.info(f"[NeuralMesh] Node {local_node_id} initialized at {local_address}")

    def join(
        self, node_id: str, address: str, metadata: Optional[Dict] = None
    ) -> NeuralNode:
        """Add a new node to the mesh."""
        if node_id in self.nodes:
            # Update existing node
            node = self.nodes[node_id]
            node.address = address
            node.last_seen = time.time()
            if metadata:
                node.metadata.update(metadata)
            return node

        # Create new node
        node = NeuralNode(
            node_id=node_id,
            address=address,
            metadata=metadata or {},
        )
        self.nodes[node_id] = node

        # Create initial synapse from local node
        self.local_node.connect(node_id)

        logger.info(f"[NeuralMesh] Node {node_id} joined at {address}")

        if self._on_node_joined:
            self._on_node_joined(node)

        return node

    def leave(self, node_id: str) -> None:
        """Remove a node from the mesh."""
        if node_id == self.local_node_id:
            logger.warning("[NeuralMesh] Cannot remove local node")
            return

        if node_id in self.nodes:
            # Remove all synapses to this node
            for node in self.nodes.values():
                node.disconnect(node_id)

            del self.nodes[node_id]

            # Invalidate routes through this node
            self._invalidate_routes_through(node_id)

            logger.info(f"[NeuralMesh] Node {node_id} left the mesh")

            if self._on_node_left:
                self._on_node_left(node_id)

    def _invalidate_routes_through(self, node_id: str) -> None:
        """Remove all cached routes that pass through a node."""
        to_remove = []
        for dest, path in self.active_routes.items():
            if node_id in path:
                to_remove.append(dest)
        for dest in to_remove:
            del self.active_routes[dest]

    def find_route(self, destination_id: str) -> Optional[List[str]]:
        """
        Find optimal route to destination using synapse fitness.
        Returns list of node IDs from local to destination.
        """
        if destination_id == self.local_node_id:
            return [self.local_node_id]

        if destination_id not in self.nodes:
            logger.warning(f"[NeuralMesh] Unknown destination: {destination_id}")
            return None

        # Check cache
        if destination_id in self.active_routes:
            return self.active_routes[destination_id]

        # Use fitness-weighted Dijkstra's algorithm
        route = self._dijkstra_route(self.local_node_id, destination_id)

        if route:
            self.active_routes[destination_id] = route
            if self._on_route_updated:
                self._on_route_updated(destination_id, route)

        return route

    def _dijkstra_route(self, start: str, end: str) -> Optional[List[str]]:
        """Find optimal route using fitness-weighted Dijkstra."""
        # Cost = 1/fitness (lower is better)
        INF = float("inf")
        costs: Dict[str, float] = {n: INF for n in self.nodes}
        costs[start] = 0.0
        prev: Dict[str, Optional[str]] = {n: None for n in self.nodes}
        unvisited: Set[str] = set(self.nodes.keys())

        while unvisited:
            # Find node with minimum cost
            current = min(unvisited, key=lambda n: costs[n])
            if costs[current] == INF:
                break
            if current == end:
                break

            unvisited.remove(current)
            node = self.nodes[current]

            # Check all synapses from current node
            for target_id, synapse in node.synapses.items():
                if target_id not in unvisited:
                    continue
                if synapse.state == SynapseState.PRUNED:
                    continue

                # Cost inversely proportional to fitness
                edge_cost = 1.0 / max(0.01, synapse.fitness)
                new_cost = costs[current] + edge_cost

                if new_cost < costs[target_id]:
                    costs[target_id] = new_cost
                    prev[target_id] = current

        # Reconstruct path
        if prev[end] is None and start != end:
            return None

        path = []
        path_node: Optional[str] = end
        while path_node is not None:
            path.append(path_node)
            path_node = prev[path_node]
        path.reverse()

        return path if path[0] == start else None

    def send_message(
        self,
        destination_id: str,
        message: bytes,
        callback: Optional[Callable[[bool, float], None]] = None,
    ) -> bool:
        """
        Send a message through the neural mesh.
        Returns True if routing was successful.
        """
        self._total_messages += 1

        route = self.find_route(destination_id)
        if not route:
            logger.warning(f"[NeuralMesh] No route to {destination_id}")
            return False

        # Simulate routing through synapses
        start_time = time.time()
        success = True
        total_latency = 0.0

        for i in range(len(route) - 1):
            source = self.nodes[route[i]]
            target_id = route[i + 1]

            synapse = source.synapses.get(target_id)
            if not synapse:
                success = False
                break

            # Simulate transmission
            hop_latency = synapse.latency_ms
            total_latency += hop_latency

            # Random failure based on reliability
            import random

            if random.random() > synapse.reliability:
                synapse.activate(success=False, latency=hop_latency)
                success = False
                # Invalidate route on failure
                if destination_id in self.active_routes:
                    del self.active_routes[destination_id]
                break

            synapse.activate(success=True, latency=hop_latency)

        elapsed_ms = (time.time() - start_time) * 1000 + total_latency

        if success:
            self._successful_routes += 1
            logger.debug(
                f"[NeuralMesh] Message to {destination_id} succeeded "
                f"(hops={len(route)-1}, latency={elapsed_ms:.1f}ms)"
            )

        if callback:
            callback(success, elapsed_ms)

        return success

    def prune_synapses(self) -> int:
        """Remove inactive synapses (synaptic pruning)."""
        pruned = 0
        for node in self.nodes.values():
            to_prune = [
                target_id
                for target_id, syn in node.synapses.items()
                if syn.should_prune(max_age_sec=self.prune_interval_sec)
            ]
            for target_id in to_prune:
                node.disconnect(target_id)
                pruned += 1

        if pruned > 0:
            logger.info(f"[NeuralMesh] Pruned {pruned} inactive synapses")

        self._last_prune = time.time()
        return pruned

    def strengthen_path(self, path: List[str], amount: float = 0.1) -> None:
        """Manually strengthen all synapses along a path."""
        for i in range(len(path) - 1):
            source = self.nodes.get(path[i])
            target_id = path[i + 1]
            if source and target_id in source.synapses:
                syn = source.synapses[target_id]
                syn.weight = min(1.0, syn.weight + amount)

    def get_topology(self) -> Dict:
        """Get current mesh topology for visualization."""
        return {
            "nodes": [
                {
                    "id": n.node_id,
                    "address": n.address,
                    "capacity": n.capacity,
                    "load": n.load,
                    "synapse_count": len(n.synapses),
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "source": syn.source_id,
                    "target": syn.target_id,
                    "weight": syn.weight,
                    "latency_ms": syn.latency_ms,
                    "fitness": syn.fitness,
                }
                for n in self.nodes.values()
                for syn in n.synapses.values()
            ],
        }

    def get_metrics(self) -> Dict:
        """Get mesh performance metrics."""
        total_synapses = sum(len(n.synapses) for n in self.nodes.values())
        avg_fitness = 0.0
        if total_synapses > 0:
            avg_fitness = (
                sum(
                    syn.fitness
                    for n in self.nodes.values()
                    for syn in n.synapses.values()
                )
                / total_synapses
            )

        return {
            "node_count": len(self.nodes),
            "synapse_count": total_synapses,
            "total_messages": self._total_messages,
            "successful_routes": self._successful_routes,
            "success_rate": (self._successful_routes / max(1, self._total_messages)),
            "average_fitness": avg_fitness,
            "cached_routes": len(self.active_routes),
        }

    # Callback registration
    def on_node_joined(self, callback: Callable[[NeuralNode], None]) -> None:
        """Register callback for node join events."""
        self._on_node_joined = callback

    def on_node_left(self, callback: Callable[[str], None]) -> None:
        """Register callback for node leave events."""
        self._on_node_left = callback

    def on_route_updated(self, callback: Callable[[str, List[str]], None]) -> None:
        """Register callback for route updates."""
        self._on_route_updated = callback


class CollectiveCompute:
    """
    Distributed computation across the Neural Mesh.
    Implements map-reduce style collective intelligence.
    """

    def __init__(self, mesh: NeuralMesh):
        self.mesh = mesh
        self._pending_tasks: Dict[str, Dict] = {}

    def compute_hash(self, task_id: str, *args: Any) -> str:
        """Generate deterministic hash for a computation task."""
        data = f"{task_id}:{':'.join(str(a) for a in args)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def scatter(
        self,
        task_id: str,
        data_chunks: List[bytes],
        target_nodes: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Distribute data chunks across mesh nodes."""
        if target_nodes is None:
            target_nodes = [
                n for n in self.mesh.nodes.keys() if n != self.mesh.local_node_id
            ]

        if len(target_nodes) == 0:
            logger.warning("[CollectiveCompute] No target nodes for scatter")
            return {}

        results = {}
        for i, chunk in enumerate(data_chunks):
            target = target_nodes[i % len(target_nodes)]
            success = self.mesh.send_message(target, chunk)
            results[target] = success

        self._pending_tasks[task_id] = {
            "type": "scatter",
            "targets": target_nodes,
            "status": results,
        }

        return results

    def gather(
        self,
        task_id: str,
        source_nodes: Optional[List[str]] = None,
    ) -> List[bytes]:
        """Collect results from mesh nodes."""
        if task_id not in self._pending_tasks:
            return []

        task = self._pending_tasks[task_id]
        if source_nodes is None:
            source_nodes = task.get("targets", [])

        # In a real implementation, this would receive actual data
        # For now, return placeholder
        results = [b"result_placeholder" for _ in source_nodes]
        return results

    def broadcast(self, message: bytes) -> int:
        """Broadcast message to all nodes. Returns count of successful sends."""
        success_count = 0
        for node_id in self.mesh.nodes:
            if node_id != self.mesh.local_node_id:
                if self.mesh.send_message(node_id, message):
                    success_count += 1
        return success_count
