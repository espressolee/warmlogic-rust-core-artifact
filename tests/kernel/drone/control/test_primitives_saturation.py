"""
Tests for Control Primitives (pid.py, filter.py).
Target: 100% Saturation.
"""

import math
import unittest

from warm_logic.kernel.drone.control.filter import LowPassFilter, NotchFilter
from warm_logic.kernel.drone.control.pid import RobustPID


class TestControlPrimitives(unittest.TestCase):
    # --- LowPassFilter Tests ---

    def test_lpf_basic(self):
        # 1Hz filter, 0.1s dt
        # Alpha calc: rc = 1/2pi = 0.159. alpha = 0.1 / (0.1+0.159) ~= 0.38
        lpf = LowPassFilter(cutoff_freq_hz=1.0, dt=0.1)
        self.assertGreater(lpf._alpha, 0.0)
        self.assertLess(lpf._alpha, 1.0)

        # Step response
        val = lpf.update(10.0)
        self.assertLess(val, 10.0)  # Should be smoothed
        self.assertGreater(val, 0.0)

        # Convergence
        for _ in range(20):
            val = lpf.update(10.0)
        self.assertAlmostEqual(val, 10.0, delta=0.1)

    def test_lpf_passthrough_invalid_config(self):
        # Zero freq -> alpha=1 (pass through)
        lpf = LowPassFilter(cutoff_freq_hz=0.0, dt=0.1)
        self.assertEqual(lpf._alpha, 1.0)
        self.assertEqual(lpf.update(5.0), 5.0)

    def test_lpf_reset(self):
        lpf = LowPassFilter(cutoff_freq_hz=1.0, dt=0.1)
        lpf.update(10.0)
        lpf.reset(initial_value=5.0)
        self.assertEqual(lpf._prev_output, 5.0)

    # --- NotchFilter Tests ---

    def test_notch_coefficients(self):
        # Standard config
        nf = NotchFilter(center_freq_hz=50.0, bandwidth_hz=10.0, sampling_freq_hz=200.0)
        # Should have valid coeffs
        self.assertNotEqual(nf._b0, 0.0)

    def test_notch_passthrough_invalid(self):
        nf = NotchFilter(center_freq_hz=0.0, bandwidth_hz=10.0, sampling_freq_hz=200.0)
        # Expect coeffs to be identity (b0=1, others 0 for numerator; a0=1 for denom)
        # Logic: _b0=1, _a0=1. _b1=_b2=_a1=_a2=0
        self.assertEqual(nf._b0, 1.0)
        self.assertEqual(nf._b1, 0.0)
        self.assertEqual(nf.update(10.0), 10.0)

    def test_notch_filtering(self):
        # Reject 50Hz signal at 200Hz sampling
        nf = NotchFilter(center_freq_hz=50.0, bandwidth_hz=5.0, sampling_freq_hz=200.0)

        # Input 50Hz sine wave
        # 200Hz -> 4 samples per cycle
        # 0, 1, 0, -1 ... amplitude 10
        # Check attenuation after settling

        amp_in = 10.0
        max_out = 0.0

        for i in range(100):
            t = i / 200.0
            val = amp_in * math.sin(2.0 * math.pi * 50.0 * t)
            out = nf.update(val)
            if i > 50:  # Check after settling
                max_out = max(max_out, abs(out))

        # Should be significantly attenuated
        self.assertLess(max_out, amp_in * 0.5)

    def test_notch_reset(self):
        nf = NotchFilter(50, 10, 200)
        nf.update(10.0)
        nf.reset()
        self.assertEqual(nf._x1, 0.0)
        self.assertEqual(nf._y1, 0.0)

    # --- RobustPID Tests ---

    def test_pid_basic_proportional(self):
        pid = RobustPID(kp=1.0, ki=0.0, kd=0.0, dt=0.1)
        out = pid.update(error=0.5)
        self.assertEqual(out, 0.5)

    def test_pid_input_limits(self):
        pid = RobustPID(
            kp=10.0, ki=0.0, kd=0.0, dt=0.1, output_max=1.0, output_min=-1.0
        )
        self.assertEqual(pid.update(0.2), 1.0)  # 2.0 -> clamped to 1.0
        self.assertEqual(pid.update(-0.2), -1.0)  # -2.0 -> clamped to -1.0

    def test_pid_integral_action_and_windup(self):
        pid = RobustPID(kp=0.0, ki=10.0, kd=0.0, dt=0.1, integrator_max=0.5)

        # Step 1: error=1.0. I += 10*1*0.1 = 1.0. Clamped to 0.5.
        out = pid.update(1.0)
        self.assertEqual(out, 0.5)
        self.assertEqual(pid._integrator, 0.5)

        # Step 2: error=-2.0. I += 10*-2*0.1 = -2.0. New I = 0.5 - 2.0 = -1.5.
        # Should clap to -0.5
        out = pid.update(-2.0)
        self.assertEqual(out, -0.5)

    def test_pid_derivative_filter(self):
        # Enable D filter
        pid = RobustPID(kp=0.0, ki=0.0, kd=1.0, dt=0.1, d_term_filter_hz=10.0)
        self.assertIsNotNone(pid._d_filter)

        # Step change in error: 0 -> 1.0
        # Raw derivative: (1-0)/0.1 = 10.0
        # Filtered should be less
        out = pid.update(1.0)
        self.assertLess(abs(out), 10.0)

    def test_pid_derivative_no_filter(self):
        pid = RobustPID(
            kp=0.0,
            ki=0.0,
            kd=1.0,
            dt=0.1,
            d_term_filter_hz=0.0,
            output_max=20.0,
            output_min=-20.0,
            integrator_max=20.0,
        )
        self.assertIsNone(pid._d_filter)

        out = pid.update(1.0)
        self.assertEqual(out, 10.0)

    def test_pid_start_with_filter(self):
        # post_init check
        pid = RobustPID(kp=1, ki=0, kd=0, dt=0.1)
        self.assertIsNotNone(pid._d_filter)  # default is 20hz

    def test_pid_reset(self):
        pid = RobustPID(kp=1, ki=1, kd=1, dt=0.1)
        pid.update(1.0)
        pid.reset()
        self.assertEqual(pid._integrator, 0.0)
        self.assertEqual(pid._prev_error, 0.0)
        if pid._d_filter:
            self.assertEqual(pid._d_filter._prev_output, 0.0)

    def test_pid_feedforward(self):
        pid = RobustPID(kp=0, ki=0, kd=0, dt=0.1)
        out = pid.update(0.0, feedforward=0.5)
        self.assertEqual(out, 0.5)
