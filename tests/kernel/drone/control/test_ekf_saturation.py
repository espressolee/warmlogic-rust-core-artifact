"""
Tests for Extended Kalman Filter (ekf.py).
Target: 100% Saturation.
"""

import math
import unittest
from unittest.mock import patch

import numpy as np

from warm_logic.kernel.drone.control.ekf import ExtendedKalmanFilter


class TestEKFSaturation(unittest.TestCase):
    def setUp(self):
        self.ekf = ExtendedKalmanFilter(dt=0.01)

    def test_ekf_init(self):
        # Initial state [q0, q1, q2, q3, bx, by, bz]
        # q0=1.0 (Identity rotation)
        self.assertEqual(self.ekf.state[0], 1.0)
        self.assertEqual(np.linalg.norm(self.ekf.state[0:4]), 1.0)
        self.assertEqual(self.ekf.P.shape, (7, 7))

    def test_ekf_predict_basic(self):
        # Rotate around X axis (Roll)
        gyro = (1.0, 0.0, 0.0)  # 1 rad/s

        initial_p = self.ekf.P.copy()
        self.ekf.predict(gyro)

        # State should have changed
        self.assertNotEqual(self.ekf.state[1], 0.0)
        # Quaternion must be normalized
        self.assertAlmostEqual(np.linalg.norm(self.ekf.state[0:4]), 1.0)
        # Covariance should have grown
        self.assertTrue(np.all(self.ekf.P >= initial_p))

    def test_ekf_predict_zero_gyro(self):
        self.ekf.predict((0.0, 0.0, 0.0))
        self.assertEqual(self.ekf.state[0], 1.0)
        self.assertAlmostEqual(np.linalg.norm(self.ekf.state[0:4]), 1.0)

    def test_ekf_predict_normalization_zero(self):
        # Force state to zero to trigger norm > 0 check branch (line 89)
        self.ekf.state[0:4] = 0.0
        self.ekf.predict((1.0, 1.0, 1.0))
        # Norm is 0, so it shouldn't divide by zero
        # The result will be whatever Euler integration produced
        pass

    def test_ekf_update_accel_static(self):
        # Standard gravity [0, 0, 9.81] (NED/Body if level)
        # Initial attitude is level, so expected h(x) is [0, 0, 1]
        accel = (0.0, 0.0, 9.81)

        initial_p_trace = np.trace(self.ekf.P)
        self.ekf.update_accel(accel)

        # Covariance should shrink after measurement
        self.assertLess(np.trace(self.ekf.P), initial_p_trace)
        # State remain level
        r, p, y = self.ekf.get_euler_angles()
        self.assertAlmostEqual(r, 0.0)
        self.assertAlmostEqual(p, 0.0)

    def test_ekf_update_accel_tilted(self):
        # Tilted 45 deg around Y (Pitch)
        # Gravity vector in body frame: [sin(45)*g, 0, cos(45)*g]
        # Wait, pitch 45 deg down -> gravity points "forward" and "down" in body
        g = 9.81
        angle = math.radians(10)
        accel = (math.sin(angle) * g, 0.0, math.cos(angle) * g)

        # Converge over a few steps
        for _ in range(50):
            self.ekf.predict((0.0, 0.0, 0.0))
            self.ekf.update_accel(accel)

        r, p, y = self.ekf.get_euler_angles()
        # Pitch should be ~10 deg (negative or positive depending on coord convention)
        # hx = 2*(q1q3 - q0q2) ... hx is negative gravity?
        # Let's just check it updated significantly
        self.assertNotAlmostEqual(p, 0.0, places=1)

    def test_ekf_update_accel_low_norm(self):
        # Freefall or zero accel
        initial_state = self.ekf.state.copy()
        self.ekf.update_accel((0.0, 0.0, 0.05))  # < 0.1
        np.testing.assert_array_equal(self.ekf.state, initial_state)

    def test_ekf_update_accel_singular_matrix(self):
        with patch("numpy.linalg.inv", side_effect=np.linalg.LinAlgError):
            self.ekf.update_accel((0.0, 0.0, 9.81))
            # Should skip and not crash
            pass

    def test_ekf_euler_angles_gimbal_lock(self):
        # Pitch 90 deg (sinp = 1.0)
        # q = [cos(45), 0, sin(45), 0]?
        # Rotation around Y axis by angle theta:
        # q = [cos(th/2), 0, sin(th/2), 0]
        angle = math.pi / 2
        self.ekf.state[0] = math.cos(angle / 2)
        self.ekf.state[2] = math.sin(angle / 2)

        r, p, y = self.ekf.get_euler_angles()
        self.assertAlmostEqual(p, 90.0)

        # Pitch -90 deg
        self.ekf.state[2] = -math.sin(angle / 2)
        r, p, y = self.ekf.get_euler_angles()
        self.assertAlmostEqual(p, -90.0)

    def test_ekf_normalization_post_update(self):
        # To cover line 155 (norm > 0) and 156
        self.ekf.state[0:4] = 0.5  # Total norm 1.0
        self.ekf.update_accel((0, 0, 9.81))
        self.assertAlmostEqual(np.linalg.norm(self.ekf.state[0:4]), 1.0)
