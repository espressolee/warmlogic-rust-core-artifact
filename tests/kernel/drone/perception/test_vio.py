"""
[Phase 140] Tests for Visual Inertial Odometry.
"""

import unittest

import numpy as np

from warm_logic.kernel.drone.perception.vio import VisualOdometry


class TestVIO(unittest.TestCase):
    def setUp(self):
        self.vio = VisualOdometry(width=10, height=10, fov_deg=90)

    def test_velocity_estimation_forward(self):
        """Moving forward should decrease depth (if looking forward)."""
        # Initial frame (Static Wall at 10m)
        frame1 = np.full((10, 10), 10.0)
        self.vio.update(frame1, dt=0.01)

        # Next frame: Drone moved forward by 1m (v=10m/s for dt=0.1s?)
        # Let's use dt=0.1 and v=10m/s -> Dist moved = 1m.
        # New depth = 9m.
        dt = 0.1
        frame2 = np.full((10, 10), 9.0)

        vel = self.vio.update(frame2, dt=dt)

        # vel[0] (Forward) should be around 10.0
        # Since alpha=0.2, it will be 0.2 * 10 = 2.0 on first step.
        self.assertGreater(vel[0], 0.0)

        # Second update to let filter converge with continuous motion
        # Target velocity is 10m/s. Each step moves 1m.
        current_depth = 9.0
        for _ in range(40):  # Increased to 40 for better filter convergence
            current_depth -= 1.0  # Moving 1m each step
            frame_i = np.full((10, 10), current_depth)
            vel = self.vio.update(frame_i, dt=dt)

        self.assertAlmostEqual(vel[0], 10.0, places=1)

    def test_velocity_estimation_backward(self):
        """Moving backward should increase depth."""
        frame1 = np.full((10, 10), 10.0)
        self.vio.update(frame1, dt=0.1)

        # New depth = 11m (moved back 1m)
        current_depth = 11.0
        for _ in range(40):  # Increased to 40
            current_depth += 1.0  # Moving 1m back each step
            frame_i = np.full((10, 10), current_depth)
            vel = self.vio.update(frame_i, dt=0.1)

        self.assertAlmostEqual(vel[0], -10.0, places=1)


if __name__ == "__main__":
    unittest.main()
