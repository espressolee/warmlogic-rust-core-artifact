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
Neural Mesh Comprehensive Tests
Tests for adaptive mesh networking with Hebbian learning.
"""

import time
import unittest

from warm_logic.kernel.mesh.neural_mesh import (
    CollectiveCompute,
    NeuralMesh,
    NeuralNode,
    Synapse,
    SynapseState,
)


class TestSynapse(unittest.TestCase):
    """Test Synapse (neural connection) behavior."""

    def test_synapse_creation(self):
        """Test basic synapse creation."""
        syn = Synapse(source_id="node_a", target_id="node_b")
        self.assertEqual(syn.source_id, "node_a")
        self.assertEqual(syn.target_id, "node_b")
        self.assertEqual(syn.weight, 0.5)
        self.assertEqual(syn.state, SynapseState.DORMANT)

    def test_synapse_weight_clamping(self):
        """Test weight is clamped to [0, 1]."""
        syn = Synapse(source_id="a", target_id="b", weight=1.5)
        self.assertEqual(syn.weight, 1.0)

        syn2 = Synapse(source_id="a", target_id="b", weight=-0.5)
        self.assertEqual(syn2.weight, 0.0)

    def test_synapse_activation_success(self):
        """Test synapse strengthens on success (Hebbian learning)."""
        syn = Synapse(source_id="a", target_id="b", weight=0.5)
        initial_weight = syn.weight

        syn.activate(success=True, latency=50.0)

        self.assertEqual(syn.activation_count, 1)
        self.assertEqual(syn.failure_count, 0)
        self.assertGreater(syn.weight, initial_weight)
        self.assertEqual(syn.state, SynapseState.POTENTIATED)

    def test_synapse_activation_failure(self):
        """Test synapse weakens on failure (depression)."""
        syn = Synapse(source_id="a", target_id="b", weight=0.5)
        initial_weight = syn.weight

        syn.activate(success=False, latency=100.0)

        self.assertEqual(syn.activation_count, 1)
        self.assertEqual(syn.failure_count, 1)
        self.assertLess(syn.weight, initial_weight)
        self.assertEqual(syn.state, SynapseState.DEPRESSED)

    def test_synapse_reliability_update(self):
        """Test reliability calculation based on failures."""
        syn = Synapse(source_id="a", target_id="b")

        # 3 successes, 1 failure
        syn.activate(success=True)
        syn.activate(success=True)
        syn.activate(success=True)
        syn.activate(success=False)

        # reliability = 1 - (1/4) = 0.75
        self.assertAlmostEqual(syn.reliability, 0.75, places=2)

    def test_synapse_latency_ema(self):
        """Test latency updates with exponential moving average."""
        syn = Synapse(source_id="a", target_id="b", latency_ms=100.0)

        syn.activate(success=True, latency=50.0)
        # EMA: (1-0.3)*100 + 0.3*50 = 85
        self.assertAlmostEqual(syn.latency_ms, 85.0, places=1)

    def test_synapse_fitness(self):
        """Test fitness calculation."""
        syn = Synapse(
            source_id="a",
            target_id="b",
            weight=0.8,
            reliability=0.9,
            latency_ms=50.0,
        )
        fitness = syn.fitness
        # fitness = weight * reliability * latency_factor
        # latency_factor = 1/(1+50/100) = 1/1.5 = 0.667
        expected = 0.8 * 0.9 * (1 / 1.5)
        self.assertAlmostEqual(fitness, expected, places=2)

    def test_synapse_should_prune(self):
        """Test pruning criteria."""
        syn = Synapse(source_id="a", target_id="b", weight=0.05)
        syn.last_activated = time.time() - 7200  # 2 hours ago

        self.assertTrue(syn.should_prune(max_age_sec=3600))

    def test_synapse_not_prune_if_strong(self):
        """Test strong synapses are not pruned."""
        syn = Synapse(source_id="a", target_id="b", weight=0.5)
        syn.last_activated = time.time() - 7200  # 2 hours ago

        self.assertFalse(syn.should_prune(max_age_sec=3600))


class TestNeuralNode(unittest.TestCase):
    """Test NeuralNode behavior."""

    def test_node_creation(self):
        """Test basic node creation."""
        node = NeuralNode(node_id="test", address="127.0.0.1:8080")
        self.assertEqual(node.node_id, "test")
        self.assertEqual(node.address, "127.0.0.1:8080")
        self.assertEqual(node.capacity, 1.0)
        self.assertEqual(len(node.synapses), 0)

    def test_node_connect(self):
        """Test creating synapse to another node."""
        node = NeuralNode(node_id="a", address="127.0.0.1:8080")
        syn = node.connect("b")

        self.assertIn("b", node.synapses)
        self.assertEqual(syn.source_id, "a")
        self.assertEqual(syn.target_id, "b")

    def test_node_connect_idempotent(self):
        """Test connecting twice returns same synapse."""
        node = NeuralNode(node_id="a", address="127.0.0.1:8080")
        syn1 = node.connect("b")
        syn2 = node.connect("b")

        self.assertIs(syn1, syn2)

    def test_node_disconnect(self):
        """Test removing synapse."""
        node = NeuralNode(node_id="a", address="127.0.0.1:8080")
        node.connect("b")
        self.assertIn("b", node.synapses)

        node.disconnect("b")
        self.assertNotIn("b", node.synapses)

    def test_node_available_capacity(self):
        """Test available capacity calculation."""
        node = NeuralNode(node_id="a", address="127.0.0.1:8080", capacity=1.0, load=0.3)
        self.assertAlmostEqual(node.available_capacity, 0.7, places=2)


class TestNeuralMesh(unittest.TestCase):
    """Test NeuralMesh network."""

    def test_mesh_initialization(self):
        """Test mesh creates local node."""
        mesh = NeuralMesh(local_node_id="local", local_address="127.0.0.1:17500")

        self.assertEqual(mesh.local_node_id, "local")
        self.assertIn("local", mesh.nodes)
        self.assertEqual(len(mesh.nodes), 1)

    def test_mesh_join_node(self):
        """Test joining a node to the mesh."""
        mesh = NeuralMesh(local_node_id="local")
        node = mesh.join("remote", "192.168.1.1:17500")

        self.assertIn("remote", mesh.nodes)
        self.assertEqual(node.address, "192.168.1.1:17500")
        # Should have synapse from local to remote
        self.assertIn("remote", mesh.local_node.synapses)

    def test_mesh_join_existing_node(self):
        """Test joining an existing node updates it."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("remote", "192.168.1.1:17500")
        node = mesh.join("remote", "192.168.1.2:17500", metadata={"version": "2"})

        self.assertEqual(node.address, "192.168.1.2:17500")
        self.assertEqual(node.metadata.get("version"), "2")

    def test_mesh_leave_node(self):
        """Test node leaving the mesh."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("remote", "192.168.1.1:17500")

        mesh.leave("remote")

        self.assertNotIn("remote", mesh.nodes)
        self.assertNotIn("remote", mesh.local_node.synapses)

    def test_mesh_leave_local_node_blocked(self):
        """Test cannot remove local node."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.leave("local")  # Should not raise

        self.assertIn("local", mesh.nodes)

    def test_mesh_find_route_to_self(self):
        """Test route to self."""
        mesh = NeuralMesh(local_node_id="local")
        route = mesh.find_route("local")

        self.assertEqual(route, ["local"])

    def test_mesh_find_route_direct(self):
        """Test direct route to neighbor."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("remote", "192.168.1.1:17500")

        route = mesh.find_route("remote")

        self.assertEqual(route, ["local", "remote"])

    def test_mesh_find_route_multi_hop(self):
        """Test multi-hop routing."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("node_a", "192.168.1.1:17500")
        mesh.join("node_b", "192.168.1.2:17500")

        # Create path: local -> node_a -> node_b
        mesh.nodes["node_a"].connect("node_b")

        route = mesh.find_route("node_b")

        # Should find a path
        self.assertIsNotNone(route)
        self.assertEqual(route[0], "local")
        self.assertEqual(route[-1], "node_b")

    def test_mesh_find_route_unknown(self):
        """Test route to unknown node."""
        mesh = NeuralMesh(local_node_id="local")
        route = mesh.find_route("unknown")

        self.assertIsNone(route)

    def test_mesh_send_message_success(self):
        """Test successful message sending."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("remote", "192.168.1.1:17500")

        # Set high reliability
        mesh.local_node.synapses["remote"].reliability = 1.0

        result = mesh.send_message("remote", b"hello")

        self.assertTrue(result)
        self.assertEqual(mesh._successful_routes, 1)

    def test_mesh_send_message_no_route(self):
        """Test message to unreachable node."""
        mesh = NeuralMesh(local_node_id="local")
        result = mesh.send_message("unknown", b"hello")

        self.assertFalse(result)

    def test_mesh_prune_synapses(self):
        """Test synaptic pruning."""
        mesh = NeuralMesh(local_node_id="local", prune_interval_sec=1.0)
        mesh.join("remote", "192.168.1.1:17500")

        # Make synapse old and weak
        syn = mesh.local_node.synapses["remote"]
        syn.weight = 0.05
        syn.last_activated = time.time() - 3600

        pruned = mesh.prune_synapses()

        self.assertEqual(pruned, 1)
        self.assertNotIn("remote", mesh.local_node.synapses)

    def test_mesh_strengthen_path(self):
        """Test manual path strengthening."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("remote", "192.168.1.1:17500")

        initial_weight = mesh.local_node.synapses["remote"].weight
        mesh.strengthen_path(["local", "remote"], amount=0.2)

        self.assertGreater(mesh.local_node.synapses["remote"].weight, initial_weight)

    def test_mesh_topology(self):
        """Test topology export."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("remote", "192.168.1.1:17500")

        topology = mesh.get_topology()

        self.assertEqual(len(topology["nodes"]), 2)
        self.assertGreaterEqual(len(topology["edges"]), 1)

    def test_mesh_metrics(self):
        """Test metrics collection."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("remote", "192.168.1.1:17500")
        mesh.local_node.synapses["remote"].reliability = 1.0
        mesh.send_message("remote", b"test")

        metrics = mesh.get_metrics()

        self.assertEqual(metrics["node_count"], 2)
        self.assertEqual(metrics["total_messages"], 1)
        self.assertGreaterEqual(metrics["synapse_count"], 1)

    def test_mesh_callbacks(self):
        """Test callback registration."""
        mesh = NeuralMesh(local_node_id="local")

        joined_nodes = []
        left_nodes = []

        mesh.on_node_joined(lambda n: joined_nodes.append(n.node_id))
        mesh.on_node_left(lambda n: left_nodes.append(n))

        mesh.join("remote", "192.168.1.1:17500")
        mesh.leave("remote")

        self.assertEqual(joined_nodes, ["remote"])
        self.assertEqual(left_nodes, ["remote"])


class TestCollectiveCompute(unittest.TestCase):
    """Test distributed computation."""

    def test_compute_hash(self):
        """Test deterministic task hashing."""
        mesh = NeuralMesh(local_node_id="local")
        compute = CollectiveCompute(mesh)

        h1 = compute.compute_hash("task1", "arg1", "arg2")
        h2 = compute.compute_hash("task1", "arg1", "arg2")
        h3 = compute.compute_hash("task2", "arg1", "arg2")

        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_scatter(self):
        """Test data distribution."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("node_a", "192.168.1.1:17500")
        mesh.join("node_b", "192.168.1.2:17500")

        # Set high reliability
        for syn in mesh.local_node.synapses.values():
            syn.reliability = 1.0

        compute = CollectiveCompute(mesh)
        results = compute.scatter("task1", [b"chunk1", b"chunk2", b"chunk3"])

        self.assertIn("node_a", results)
        self.assertIn("node_b", results)

    def test_scatter_no_targets(self):
        """Test scatter with no target nodes."""
        mesh = NeuralMesh(local_node_id="local")
        compute = CollectiveCompute(mesh)

        results = compute.scatter("task1", [b"chunk1"])

        self.assertEqual(results, {})

    def test_gather(self):
        """Test result collection."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("node_a", "192.168.1.1:17500")

        for syn in mesh.local_node.synapses.values():
            syn.reliability = 1.0

        compute = CollectiveCompute(mesh)
        compute.scatter("task1", [b"chunk1"])

        results = compute.gather("task1")

        self.assertGreaterEqual(len(results), 1)

    def test_broadcast(self):
        """Test message broadcast."""
        mesh = NeuralMesh(local_node_id="local")
        mesh.join("node_a", "192.168.1.1:17500")
        mesh.join("node_b", "192.168.1.2:17500")

        for syn in mesh.local_node.synapses.values():
            syn.reliability = 1.0

        compute = CollectiveCompute(mesh)
        count = compute.broadcast(b"broadcast message")

        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
