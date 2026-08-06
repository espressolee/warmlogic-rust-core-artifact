"""
[Phase 201] Tests for Minimum-Jerk Trajectory Generator.
Target: 100% Saturation.
"""

import unittest

import numpy as np

from warm_logic.kernel.drone.control.trajectory import (
    QuinticSpline,
    TrajectoryGenerator,
)


class TestTrajectorySaturation(unittest.TestCase):
    def test_quintic_spline_zero_duration(self):
        # Line 28-30: duration <= 0
        qs = QuinticSpline(1.0, 0.1, 0.01, 2.0, 0.2, 0.02, 0.0)
        self.assertEqual(qs.T, 0.0)
        np.testing.assert_array_equal(qs.coeffs, [1.0, 0, 0, 0, 0, 0])

        # Sampling should return start_pos
        p, v, a = qs.sample(0.1)
        self.assertEqual(p, 1.0)
        self.assertEqual(v, 0.0)
        self.assertEqual(a, 0.0)

    def test_quintic_spline_singular_matrix(self):
        # Try to trigger LinAlgError in solve (Line 63-64)
        # We can mock np.linalg.solve
        from unittest.mock import patch

        with patch("numpy.linalg.solve", side_effect=np.linalg.LinAlgError):
            qs = QuinticSpline(1, 0, 0, 2, 0, 0, 5.0)
            np.testing.assert_array_equal(qs.coeffs, [1.0, 0, 0, 0, 0, 0])

    def test_quintic_spline_sample_boundaries(self):
        qs = QuinticSpline(0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 10.0)

        # t <= 0 (Line 68-69)
        p, v, a = qs.sample(-1.0)
        self.assertEqual(p, 0.0)
        self.assertEqual(v, 0.0)
        self.assertEqual(a, 0.0)

        # t >= T (Line 70-72)
        p, v, a = qs.sample(11.0)
        self.assertAlmostEqual(p, 10.0)
        self.assertAlmostEqual(v, 0.0)
        self.assertAlmostEqual(a, 0.0)

    def test_trajectory_generator_inactive(self):
        # Line 163-164
        tg = TrajectoryGenerator()
        p, v, a = tg.sample(100.0)
        self.assertIsNone(p)
        self.assertIsNone(v)
        self.assertIsNone(a)

    def test_trajectory_generator_basic(self):
        tg = TrajectoryGenerator()
        start_pos = np.array([0, 0, 0])
        start_vel = np.array([0, 0, 0])
        start_accel = np.array([0, 0, 0])
        target_pos = np.array([10, 20, 30])

        tg.generate(
            start_pos,
            start_vel,
            start_accel,
            target_pos,
            duration=10.0,
            start_time=100.0,
        )
        self.assertTrue(tg.active)

        # Sample at midpoint
        p, v, a = tg.sample(105.0)
        self.assertIsNotNone(p)
        self.assertEqual(len(p), 3)
        self.assertGreater(p[0], 0)

        # Sample at end (Line 167-168)
        p, v, a = tg.sample(115.0)
        self.assertAlmostEqual(p[0], 10.0)
        self.assertAlmostEqual(p[1], 20.0)
        self.assertAlmostEqual(p[2], 30.0)


if __name__ == "__main__":
    unittest.main()
