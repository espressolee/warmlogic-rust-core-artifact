# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""
[P3xx] Unit tests for swarm kinetic engine.
Tests: kinetic.py - Boids-inspired multi-drone coordination
"""

import time
import unittest
from unittest import mock

import numpy as np

from warm_logic.kernel.swarm.kinetic import KineticSwarmEngine, SwarmPeerState


class TestSwarmPeerState(unittest.TestCase):
    """Test SwarmPeerState dataclass."""

    def test_peer_state_creation(self):
        """Test creating a peer state."""
        state = SwarmPeerState(
            node_id="drone1",
            position_ned=np.array([10.0, 20.0, -5.0]),
            velocity_ned=np.array([1.0, 0.5, 0.0]),
        )
        self.assertEqual(state.node_id, "drone1")
        np.testing.assert_array_equal(state.position_ned, [10.0, 20.0, -5.0])

    def test_peer_state_timestamp(self):
        """Test peer state has valid timestamp."""
        before = time.time()
        state = SwarmPeerState(
            node_id="drone2",
            position_ned=np.zeros(3),
            velocity_ned=np.zeros(3),
        )
        after = time.time()
        self.assertGreaterEqual(state.last_update, before)
        self.assertLessEqual(state.last_update, after)


class TestKineticSwarmEngine(unittest.TestCase):
    """Test KineticSwarmEngine."""

    def setUp(self):
        """Create engine instance."""
        self.engine = KineticSwarmEngine(node_id="drone0")

    def test_init_defaults(self):
        """Test engine initialization defaults."""
        self.assertEqual(self.engine.node_id, "drone0")
        self.assertEqual(len(self.engine.peers), 0)
        self.assertFalse(self.engine.formation_active)
        self.assertEqual(self.engine.formation_type, "V-SHAPE")

    def test_init_boids_weights(self):
        """Test boids weight initialization."""
        self.assertEqual(self.engine.weight_separation, 1.5)
        self.assertEqual(self.engine.weight_alignment, 1.0)
        self.assertEqual(self.engine.weight_cohesion, 1.0)

    def test_init_boids_radii(self):
        """Test boids radii initialization."""
        self.assertEqual(self.engine.radius_separation, 5.0)
        self.assertEqual(self.engine.radius_alignment, 20.0)
        self.assertEqual(self.engine.radius_cohesion, 30.0)

    def test_update_peer_adds_new(self):
        """Test adding a new peer."""
        self.engine.update_peer("drone1", (10.0, 20.0, 0.0), (1.0, 0.0, 0.0))
        self.assertEqual(len(self.engine.peers), 1)
        self.assertIn("drone1", self.engine.peers)

    def test_update_peer_ignores_self(self):
        """Test updating self is ignored."""
        self.engine.update_peer("drone0", (10.0, 20.0, 0.0), (1.0, 0.0, 0.0))
        self.assertEqual(len(self.engine.peers), 0)

    def test_update_peer_updates_existing(self):
        """Test updating an existing peer."""
        self.engine.update_peer("drone1", (10.0, 20.0, 0.0), (1.0, 0.0, 0.0))
        self.engine.update_peer("drone1", (15.0, 25.0, 0.0), (2.0, 0.0, 0.0))
        self.assertEqual(len(self.engine.peers), 1)
        np.testing.assert_array_equal(
            self.engine.peers["drone1"].position_ned, [15.0, 25.0, 0.0]
        )

    def test_calculate_swarm_force_no_peers(self):
        """Test swarm force with no peers."""
        my_pos = np.array([0.0, 0.0, 0.0])
        my_vel = np.array([1.0, 0.0, 0.0])
        force = self.engine.calculate_swarm_force(my_pos, my_vel)
        np.testing.assert_array_equal(force, np.zeros(3))

    def test_calculate_swarm_force_with_peers(self):
        """Test swarm force calculation with peers."""
        self.engine.update_peer("drone1", (20.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        my_pos = np.array([0.0, 0.0, 0.0])
        my_vel = np.array([1.0, 0.0, 0.0])
        force = self.engine.calculate_swarm_force(my_pos, my_vel)
        # Should have cohesion component pulling toward peer
        self.assertIsInstance(force, np.ndarray)
        self.assertEqual(len(force), 3)

    def test_separation_force(self):
        """Test separation force calculation."""
        # Add peer very close
        self.engine.update_peer("drone1", (3.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        my_pos = np.array([0.0, 0.0, 0.0])
        force = self.engine._calculate_separation(my_pos)
        # Should push away from peer (negative X)
        self.assertLess(force[0], 0)

    def test_alignment_force(self):
        """Test alignment force calculation."""
        self.engine.update_peer("drone1", (20.0, 0.0, 0.0), (5.0, 0.0, 0.0))
        my_vel = np.array([1.0, 0.0, 0.0])
        force = self.engine._calculate_alignment(my_vel)
        # Should want to match peer velocity (faster)
        self.assertGreater(force[0], 0)

    def test_cohesion_force(self):
        """Test cohesion force calculation."""
        self.engine.update_peer("drone1", (20.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        my_pos = np.array([0.0, 0.0, 0.0])
        force = self.engine._calculate_cohesion(my_pos)
        # Should want to move toward peer (positive X)
        self.assertGreater(force[0], 0)

    def test_formation_offset_inactive(self):
        """Test formation offset when formation inactive."""
        self.engine.formation_active = False
        offset = self.engine.get_formation_offset()
        np.testing.assert_array_equal(offset, np.zeros(3))

    def test_formation_offset_v_shape_leader(self):
        """Test V-shape formation offset for leader (index 0)."""
        self.engine.formation_active = True
        self.engine.formation_type = "V-SHAPE"
        self.engine.formation_index = 0
        offset = self.engine.get_formation_offset()
        # Leader at tip should be at origin
        np.testing.assert_array_equal(offset, np.zeros(3))

    def test_stale_peer_cleanup(self):
        """Test stale peers are cleaned up."""
        # Add peer with old timestamp
        with mock.patch("time.time", return_value=100.0):
            self.engine.update_peer("drone1", (10.0, 0.0, 0.0), (0.0, 0.0, 0.0))

        # Update with new time (3 seconds later, beyond 2s threshold)
        with mock.patch("time.time", return_value=103.0):
            self.engine.update_peer("drone2", (20.0, 0.0, 0.0), (0.0, 0.0, 0.0))

        # drone1 should be cleaned up
        self.assertNotIn("drone1", self.engine.peers)
        self.assertIn("drone2", self.engine.peers)


class TestSwarmIntegration(unittest.TestCase):
    """Integration tests for swarm coordination."""

    def test_multi_drone_scenario(self):
        """Test realistic multi-drone scenario."""
        engine = KineticSwarmEngine(node_id="leader")

        # Add wingmen
        engine.update_peer("wing1", (10.0, 10.0, 0.0), (5.0, 0.0, 0.0))
        engine.update_peer("wing2", (10.0, -10.0, 0.0), (5.0, 0.0, 0.0))

        # Calculate force for leader
        leader_pos = np.array([0.0, 0.0, 0.0])
        leader_vel = np.array([5.0, 0.0, 0.0])
        force = engine.calculate_swarm_force(leader_pos, leader_vel)

        # Force should be finite and 3D
        self.assertFalse(np.any(np.isnan(force)))
        self.assertFalse(np.any(np.isinf(force)))
        self.assertEqual(len(force), 3)

    def test_swarm_weights_configurable(self):
        """Test swarm behavior weights are configurable."""
        engine = KineticSwarmEngine(node_id="test")
        engine.weight_separation = 2.0
        engine.weight_alignment = 0.5
        engine.weight_cohesion = 0.5

        self.assertEqual(engine.weight_separation, 2.0)
        self.assertEqual(engine.weight_alignment, 0.5)


if __name__ == "__main__":
    unittest.main()
