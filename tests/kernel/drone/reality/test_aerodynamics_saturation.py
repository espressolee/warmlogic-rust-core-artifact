"""
Saturation Tests for Aerodynamics Module.
Targets: bemt.py, vrs.py, ground_effect.py
"""

import math
import unittest

from warm_logic.kernel.drone.reality.aerodynamics.bemt import (
    AirfoilData,
    BladeElementMomentumTheory,
    BladeGeometry,
)
from warm_logic.kernel.drone.reality.aerodynamics.ground_effect import (
    GroundEffect,
    WallEffect,
)
from warm_logic.kernel.drone.reality.aerodynamics.vrs import VortexRingState, VRSState


class TestBEMTSaturation(unittest.TestCase):
    def setUp(self):
        self.bemt = BladeElementMomentumTheory()

    def test_blade_geometry_props(self):
        bg = BladeGeometry(radius_m=1.0, chord_m=0.1, num_blades=2)
        self.assertAlmostEqual(bg.disk_area_m2, math.pi)
        self.assertAlmostEqual(bg.solidity, 2 * 0.1 / (math.pi * 1.0))

    def test_airfoil_data(self):
        ad = AirfoilData()
        # Linear region
        self.assertAlmostEqual(ad.get_cl(0), 0.0)
        self.assertAlmostEqual(ad.get_cl(5.0), 5.73 * math.radians(5.0))
        # Stall region
        cl_stall = ad.get_cl(15.0)
        self.assertTrue(abs(cl_stall) <= ad.cl_max)

        # Drag
        self.assertGreater(ad.get_cd(0), 0.0)
        self.assertEqual(ad.get_cd(15.0), ad.cd_stall)

    def test_calculate_ct_zero_speed(self):
        ct = self.bemt.calculate_ct(rpm=0, rho=1.225)
        self.assertEqual(ct, 0.0)

    def test_calculate_thrust_power_fom(self):
        # Normal operation
        thrust = self.bemt.calculate_thrust(rpm=5000, rho=1.225)
        self.assertGreater(thrust, 0)

        power = self.bemt.calculate_power(rpm=5000, rho=1.225)
        self.assertGreater(power, 0)

        fom = self.bemt.calculate_figure_of_merit(rpm=5000, rho=1.225)
        self.assertTrue(0 < fom <= 1.0)

        # Performance tuple
        t, p, f = self.bemt.calculate_performance(rpm=5000)
        self.assertEqual(t, thrust)

    def test_calculate_power_static_zero_thrust(self):
        # Force 0 thrust case
        power = self.bemt.calculate_power(rpm=0, rho=1.225)
        self.assertEqual(power, 0.0)

    def test_figure_of_merit_zero_rpm(self):
        # Cover T <= 0 or P <= 0 branch
        fom = self.bemt.calculate_figure_of_merit(rpm=0, rho=1.225)
        self.assertEqual(fom, 0.0)


class TestVRSSaturation(unittest.TestCase):
    def setUp(self):
        self.vrs = VortexRingState()

    def test_post_init(self):
        v = VortexRingState(rotor_radius_m=1.0)
        self.assertAlmostEqual(v.rotor_disk_area_m2, math.pi)

    def test_hover_induced_velocity(self):
        # v_h = sqrt(T / 2rhoA)
        # T=10, rho=1, A=1 -> v_h = sqrt(5)
        self.vrs.rotor_disk_area_m2 = 1.0
        vh = self.vrs.get_hover_induced_velocity(thrust_n=10.0, rho=1.0)
        self.assertAlmostEqual(vh, math.sqrt(5.0))

        # Zero/Neg thrust
        self.assertEqual(self.vrs.get_hover_induced_velocity(0, 1.0), 0.0)
        self.assertEqual(self.vrs.get_hover_induced_velocity(-5, 1.0), 0.0)

    def test_check_state_transitions(self):
        # 1. Low induced velocity (v_h < 0.1) -> CLEAR
        state = self.vrs.check_state(0, 0, thrust_n=0.001)
        self.assertEqual(state, VRSState.CLEAR)

        # Setup standard conditions
        # v_h approx 4.0 m/s for T=10, rho=1.225, r=0.127
        vh = self.vrs.get_hover_induced_velocity(10.0, 1.225)

        # 2. CLEAR (Low descent)
        state = self.vrs.check_state(
            v_descent_m_s=0.1 * vh, v_forward_m_s=0, thrust_n=10.0
        )
        self.assertEqual(state, VRSState.CLEAR)

        # 3. ONSET (0.7 < vd/vh < 1.0)
        state = self.vrs.check_state(
            v_descent_m_s=0.8 * vh, v_forward_m_s=0, thrust_n=10.0
        )
        self.assertEqual(state, VRSState.ONSET)

        # 4. DEVELOPED (1.0 < vd/vh < 1.7)
        state = self.vrs.check_state(
            v_descent_m_s=1.2 * vh, v_forward_m_s=0, thrust_n=10.0
        )
        self.assertEqual(state, VRSState.DEVELOPED)

        # 5. WINDMILL_BRAKE (vd/vh > 1.7)
        state = self.vrs.check_state(
            v_descent_m_s=2.0 * vh, v_forward_m_s=0, thrust_n=10.0
        )
        self.assertEqual(state, VRSState.WINDMILL_BRAKE)

        # 6. CLEAR (High forward speed > 1.5 vh)
        state = self.vrs.check_state(
            v_descent_m_s=1.2 * vh, v_forward_m_s=2.0 * vh, thrust_n=10.0
        )
        self.assertEqual(state, VRSState.CLEAR)

    def test_thrust_reduction(self):
        # Mock check_state via input values logic
        # Clear
        self.assertEqual(self.vrs.get_thrust_reduction(0, 0, 10.0), 1.0)
        # Onset
        vh = self.vrs.get_hover_induced_velocity(10.0, 1.225)
        self.assertEqual(self.vrs.get_thrust_reduction(0.8 * vh, 0, 10.0), 0.85)
        # Developed
        self.assertEqual(self.vrs.get_thrust_reduction(1.2 * vh, 0, 10.0), 0.40)
        # Windmill
        self.assertEqual(self.vrs.get_thrust_reduction(2.0 * vh, 0, 10.0), 0.20)

    def test_vibration_level(self):
        self.assertEqual(self.vrs.get_vibration_level(0, 0, 10.0), 1.0)
        vh = self.vrs.get_hover_induced_velocity(10.0, 1.225)
        self.assertEqual(self.vrs.get_vibration_level(1.2 * vh, 0, 10.0), 10.0)


class TestGroundEffectSaturation(unittest.TestCase):
    def setUp(self):
        self.ge = GroundEffect()
        self.we = WallEffect()

    def test_ground_effect_ratio(self):
        # High altitude -> 1.0
        self.assertEqual(self.ge.get_thrust_ratio(100.0), 1.0)
        # Low altitude -> > 1.0
        ratio = self.ge.get_thrust_ratio(0.1)
        self.assertGreater(ratio, 1.0)
        self.assertLessEqual(ratio, 1.5)

        # Power ratio
        pr = self.ge.get_power_ratio(0.1)
        self.assertLess(pr, 1.0)

    def test_wall_effect(self):
        # Far wall -> 0
        self.assertEqual(self.we.get_lateral_force_coefficient(10.0), 0.0)
        # Near wall -> > 0
        coeff = self.we.get_lateral_force_coefficient(0.1)
        self.assertGreater(coeff, 0.0)
