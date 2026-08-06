"""
Stabilization Tests (Phase 120 Step 1).

Verifies Filter, PID, and EKF implementations for robust control.
"""

import math
import unittest

import numpy as np

from warm_logic.kernel.drone.control.ekf import ExtendedKalmanFilter
from warm_logic.kernel.drone.control.filter import LowPassFilter, NotchFilter
from warm_logic.kernel.drone.control.pid import RobustPID


class TestStabilization(unittest.TestCase):
    def test_low_pass_filter(self):
        """Verify Low Pass Filter step response."""
        dt = 0.01
        cutoff = 1.0  # 1Hz
        lpf = LowPassFilter(cutoff_freq_hz=cutoff, dt=dt)

        # Step input 0 -> 1
        val = 0.0
        output = 0.0

        # After 1 time constant (RC = 1/2pi*1 = 0.159s)
        # Output should be approx 63.2%
        steps = int(0.159 / dt)
        for _ in range(steps):
            output = lpf.update(1.0)

        self.assertAlmostEqual(output, 0.632, delta=0.05)

    def test_notch_filter(self):
        """Verify Notch Filter removes target frequency."""
        dt = 0.001  # 1kHz
        center = 50.0  # 50Hz notch
        notch = NotchFilter(
            center_freq_hz=center, bandwidth_hz=5.0, sampling_freq_hz=1000.0
        )

        # Generate 50Hz sine wave
        # signal = sin(2*pi*50*t)

        max_amp = 0.0
        for i in range(1000):  # 1 second
            t = i * dt
            signal = math.sin(2 * math.pi * 50 * t)
            output = notch.update(signal)

            # Allow settling time
            if i > 500:
                max_amp = max(max_amp, abs(output))

        # Should be heavily attenuated
        self.assertLess(max_amp, 0.1)

        # Pass 10Hz signal (Should pass)
        notch.reset()
        max_amp = 0.0
        for i in range(1000):
            t = i * dt
            signal = math.sin(2 * math.pi * 10 * t)
            output = notch.update(signal)
            if i > 500:
                max_amp = max(max_amp, abs(output))

        self.assertGreater(max_amp, 0.9)

    def test_pid_anti_windup(self):
        """Verify PID integrator clamping."""
        pid = RobustPID(kp=1.0, ki=1.0, kd=0.0, dt=0.1, integrator_max=0.5)

        # Large error for long time
        for _ in range(100):
            pid.update(error=10.0)

        # Integrator should be clamped at 0.5
        # P term = 10.0, I term = 0.5 -> Output = 10.5 -> Clamped to output_max (1.0)

        # Access private member for testing
        self.assertAlmostEqual(pid._integrator, 0.5)

    def test_ekf_convergence(self):
        """Verify EKF converges to correct attitude from gravity."""
        ekf = ExtendedKalmanFilter(dt=0.01)

        # Pitch up 90 degrees scenario (Gravity on X-axis)
        # Body Frame Accel: [g, 0, 0] approx (if pitched up 90 deg)
        # Wait, if pitched up 90 deg, nose is up. Gravity vector [0, 0, 1] in NED.
        # R(0, 90, 0) rotates NED to Body.
        # Body accel measures reaction force. So [1g, 0, 0].

        # Let's test simple 0 degree (Level) first
        # Accel measures [0, 0, 9.8] approximately (reaction force upwards)
        # So Normalized z = [0, 0, 1]

        # Initial slightly off state
        ekf.state[1] = 0.1  # Small roll error

        # Update with [0, 0, 9.8] for 1 second
        for _ in range(100):
            ekf.predict((0.0, 0.0, 0.0))
            ekf.update_accel((0.0, 0.0, 9.8))

        r, p, y = ekf.get_euler_angles()
        self.assertAlmostEqual(r, 0.0, delta=1.0)
        self.assertAlmostEqual(p, 0.0, delta=1.0)

        # Test 45 degree Roll
        # Gravity vector in body: [0, sin(45)g, cos(45)g]
        # z = [0, 0.707, 0.707]

        g = 9.8
        val = g * math.sin(math.radians(45))

        ekf = ExtendedKalmanFilter(dt=0.01)
        for _ in range(200):  # 2 seconds
            ekf.predict((0.0, 0.0, 0.0))
            ekf.update_accel((0.0, val, val))

        r, p, y = ekf.get_euler_angles()
        self.assertAlmostEqual(r, 45.0, delta=2.0)
