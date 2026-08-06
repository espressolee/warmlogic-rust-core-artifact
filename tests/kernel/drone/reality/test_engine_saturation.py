"""
Saturation Tests for Reality Engine Integration.
Targets: engine.py
"""

import unittest

from warm_logic.kernel.drone.reality.aerodynamics import VRSState
from warm_logic.kernel.drone.reality.engine import RealityEngine, SimulationState


class TestRealityEngineSaturation(unittest.TestCase):
    def setUp(self):
        self.engine = RealityEngine()
        self.state = SimulationState()

    def test_state_defaults(self):
        s = SimulationState()
        self.assertEqual(s.latitude_deg, 0.0)
        self.assertEqual(s.time_s, 0.0)
        self.assertEqual(len(s.motor_rpms), 4)

    def test_simulate_step_structure(self):
        # Run one step
        dt = 0.01
        result = self.engine.simulate_step(self.state, dt)

        # Verify Keys
        expected_keys = [
            "atmosphere",
            "wind",
            "gravity",
            "coriolis",
            "propulsion",
            "ground_effect",
            "vrs",
            "sensors",
            "faults",
        ]
        for k in expected_keys:
            self.assertIn(k, result)

        # Verify State Update
        self.assertAlmostEqual(self.state.time_s, dt)
        self.assertEqual(self.engine.timer.current_value, int(dt * 1_000_000))

    def test_simulate_step_physics_flow(self):
        # Set specific state to trigger logic
        self.state.altitude_m = 0.1  # Low altitude -> Ground effect (z/R < 4)
        self.state.velocity_d_m_s = 5.0  # Descent -> VRS check
        self.state.throttle = (1.0, 1.0, 1.0, 1.0)  # Full throttle -> Propulsion

        dt = 0.1
        result = self.engine.simulate_step(self.state, dt)

        # Check Ground Effect: integration output should match model at updated state.
        expected_ground_effect = self.engine.ground_effect.get_thrust_ratio(
            self.state.altitude_m
        )
        self.assertGreaterEqual(result["ground_effect"], 1.0)
        self.assertAlmostEqual(result["ground_effect"], expected_ground_effect, places=6)

        # Check Propulsion
        prop = result["propulsion"]
        self.assertGreater(prop["total_thrust_n"], 0)

        # Check Sensors
        sensors = result["sensors"]
        self.assertIn("gps_pos", sensors)
        self.assertIn("imu_accel", sensors)

    def test_reset(self):
        # Change internal state
        self.engine.battery.soc = 0.5
        self.engine.reset()

        self.assertEqual(self.engine.battery.soc, 1.0)
        self.assertEqual(self.engine.timer.current_value, 0)
