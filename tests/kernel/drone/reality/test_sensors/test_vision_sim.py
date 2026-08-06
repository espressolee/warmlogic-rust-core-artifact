"""
[Phase 140] Tests for Vision Simulator.
"""

import unittest

import numpy as np

from warm_logic.kernel.drone.reality.sensors.vision_sim import Obstacle, VisionSimulator


class TestVisionSim(unittest.TestCase):
    def setUp(self):
        self.vision = VisionSimulator(width=10, height=10, fov_deg=90)

    def test_ray_init(self):
        """Verify ray directions are unit vectors and have correct shape."""
        self.assertEqual(self.vision.ray_directions.shape, (10, 10, 3))
        # Center ray should be [1, 0, 0] in camera frame (X-forward)
        center_ray = self.vision.ray_directions[5, 5]
        # It won't be EXACTLY [1,0,0] because 10 is even, center is between 4 and 5
        # But it should be close.
        self.assertGreater(center_ray[0], 0.9)

        # Norms should be 1.0
        for v in range(10):
            for u in range(10):
                self.assertAlmostEqual(
                    np.linalg.norm(self.vision.ray_directions[v, u]), 1.0
                )

    def test_ground_intersection(self):
        """Drone at 50m altitude, looking straight down."""
        # Note: Camera is X-forward in body frame.
        # To look down, we need to pitch the drone 90 degrees.
        pos = np.array([0.0, 0.0, -50.0])
        attitude = np.array([0.0, -90.0, 0.0])  # Pitch -90 (Down)

        depth_map = self.vision.render_depth(pos, attitude)

        # The center pixel should be exactly 50m
        # Because we are at -50m and looking at D=0.
        # Wait, pitch 90 means X points Down.
        self.assertAlmostEqual(depth_map[5, 5], 50.0, places=1)

    def test_obstacle_intersection(self):
        """Place an obstacle directly in front of the drone."""
        self.vision.obstacles = [Obstacle("Target", np.array([10.0, 0.0, 0.0]), 2.0)]
        # Drone at origin, looking forward (0,0,0)
        pos = np.array([0.0, 0.0, 0.0])
        attitude = np.array([0.0, 0.0, 0.0])

        depth_map = self.vision.render_depth(pos, attitude)

        # Center should hit the sphere surface at 10 - 2 = 8m
        # Ray is [1,0,0], sphere at [10,0,0] radius 2.
        # Intersection at t=8.
        self.assertAlmostEqual(depth_map[5, 5], 8.0, places=0)

    def test_rotation_matrix(self):
        """Verify Euler to Rotation conversion."""
        # 90 deg yaw
        R = self.vision._euler_to_rotation_matrix(np.array([0, 0, 90]))
        vec = np.array([1.0, 0.0, 0.0])  # Body Forward
        ned_vec = R @ vec
        # NED Forward should be East (0, 1, 0)
        self.assertAlmostEqual(ned_vec[0], 0.0)
        self.assertAlmostEqual(ned_vec[1], 1.0)
        self.assertAlmostEqual(ned_vec[2], 0.0)


if __name__ == "__main__":
    unittest.main()
