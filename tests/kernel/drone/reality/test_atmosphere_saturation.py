"""
Saturation Tests for Atmosphere Module.
Targets: wind.py, us_standard_1976.py
"""

import math
import unittest

from warm_logic.kernel.drone.reality.atmosphere.us_standard_1976 import (
    AtmosphericState,
    USStandardAtmosphere1976,
)
from warm_logic.kernel.drone.reality.atmosphere.wind import (
    DrydenTurbulence,
    VonKarmanTurbulence,
)


class TestWindSaturation(unittest.TestCase):
    def test_dryden_low_altitude(self):
        # Below 1000ft (304.8m)
        dt = DrydenTurbulence(
            altitude_m=100.0, airspeed_m_s=20.0, turbulence_intensity="moderate"
        )
        self.assertLess(dt.L_u, 533.4)

        # Sample
        u, v, w = dt.sample(0.01)
        self.assertIsInstance(u, float)

        # Reset
        dt.reset()
        self.assertEqual(dt._u_state, 0.0)

    def test_dryden_high_altitude_intensities(self):
        # Above 1000ft
        alt = 500.0

        # Moderate
        dt_mod = DrydenTurbulence(altitude_m=alt, turbulence_intensity="moderate")
        self.assertEqual(dt_mod.L_u, 533.4)
        self.assertEqual(dt_mod.sigma_u, 1.5)

        # Light
        dt_light = DrydenTurbulence(altitude_m=alt, turbulence_intensity="light")
        self.assertEqual(dt_light.sigma_u, 0.5)

        # Severe
        dt_sev = DrydenTurbulence(altitude_m=alt, turbulence_intensity="severe")
        self.assertEqual(dt_sev.sigma_u, 3.0)

        # Default fallback
        dt_def = DrydenTurbulence(altitude_m=alt, turbulence_intensity="unknown")
        self.assertEqual(dt_def.sigma_u, 1.5)

    def test_dryden_zero_time_constants(self):
        # Creating edge case where tau might be 0?
        # V=0 -> but code has max(1.0, V).
        # L_u = 0? if h=0?
        dt = DrydenTurbulence(altitude_m=0.0, airspeed_m_s=20.0)
        u, v, w = dt.sample(0.01)
        # Should not crash division by zero

    def test_dryden_get_wind_speed_20ft(self):
        dt = DrydenTurbulence()
        # Coverage for _get_wind_speed_at_20ft dictionary
        dt.turbulence_intensity = "light"
        self.assertEqual(dt._get_wind_speed_at_20ft(), 7.7)
        dt.turbulence_intensity = "severe"
        self.assertEqual(dt._get_wind_speed_at_20ft(), 23.2)
        dt.turbulence_intensity = "custom"
        self.assertEqual(dt._get_wind_speed_at_20ft(), 15.4)

    def test_von_karman(self):
        vk = VonKarmanTurbulence(altitude_m=100.0)
        u, v, w = vk.sample(0.01)
        self.assertNotEqual(
            u, 0.0
        )  # Probabilistic, but highly likely non-zero after 1 step if noise is generated

        vk.reset()
        # Check internal state reset
        self.assertEqual(vk._dryden._u_state, 0.0)
        # Verify filter states list reset
        self.assertEqual(len(vk._filter_states), 10)
        self.assertEqual(vk._filter_states[0], 0.0)


class TestUSStandardAtmosphereSaturation(unittest.TestCase):
    def setUp(self):
        self.atm = USStandardAtmosphere1976()

    def test_layers_coverage(self):
        # 0. Troposphere (0-11km) -> Gradient
        h0 = 5000
        t0 = self.atm.get_temperature(h0)
        self.assertAlmostEqual(t0, 288.15 - 0.0065 * 5000)

        # 1. Tropopause (11-20km) -> Isothermal
        h1 = 15000
        t1 = self.atm.get_temperature(h1)
        self.assertAlmostEqual(t1, 216.65)
        # Pressure formula for isothermal
        p1 = self.atm.get_pressure(h1)
        self.assertGreater(p1, 0)

        # 2. Stratosphere 1 (20-32km) -> Gradient Positive
        h2 = 25000
        t2 = self.atm.get_temperature(h2)
        self.assertGreater(t2, 216.65)

        # 3. Stratosphere 2 (32-47km) -> Gradient Positive
        h3 = 40000
        t3 = self.atm.get_temperature(h3)
        self.assertGreater(t3, 228.65)

        # 4. Stratopause (47-51km) -> Isothermal
        h4 = 50000
        t4 = self.atm.get_temperature(h4)
        self.assertAlmostEqual(t4, 270.65)

        # 5. Mesosphere 1 (51-71km) -> Gradient Negative
        h5 = 60000
        t5 = self.atm.get_temperature(h5)
        self.assertLess(t5, 270.65)

        # 6. Mesosphere 2 (71-86km) -> Gradient Negative
        h6 = 80000
        t6 = self.atm.get_temperature(h6)
        self.assertLess(t6, 214.65)  # Wait, base is 214.65 at 71km?
        # Layer 6: (71000, 214.65, -0.002)
        # So at 80km it should be lower. Correct.

    def test_clamped_altitude(self):
        # Test bounds
        t_low = self.atm.get_temperature(-100)
        self.assertEqual(t_low, 288.15)

        t_high = self.atm.get_temperature(100000)
        # Max is 86km logic in get_temperature? "min(altitude_m, 86000)"
        # At 86km (top of Mesosphere 2): 214.65 + (-0.002)*(86000-71000) = 214.65 - 30 = 184.65
        self.assertAlmostEqual(t_high, 184.65)

    def test_derived_quantities(self):
        h = 0.0
        # Density
        rho = self.atm.get_density(h)
        self.assertAlmostEqual(rho, 1.225, places=3)

        # Speed of Sound
        a = self.atm.get_speed_of_sound(h)
        self.assertAlmostEqual(a, 340.29, places=1)

        # Viscosity
        mu = self.atm.get_dynamic_viscosity(h)
        self.assertGreater(mu, 0)

        nu = self.atm.get_kinematic_viscosity(h)
        self.assertGreater(nu, 0)

        # Full state
        state = self.atm.get_state(h)
        self.assertIsInstance(state, AtmosphericState)
        self.assertEqual(state.altitude_m, 0.0)

    def test_layer_index_logic(self):
        # Hit boundary conditions precisely?
        # 11000
        idx = self.atm.get_layer_index(11000)
        self.assertEqual(idx, 1)  # Should fall into second layer?
        # Logic: if altitude_m >= self.LAYERS[i][0] -> return i (iterating backwards)
        # LAYERS[1] is (11000, ...)
        # So 11000 >= 11000 -> returns 1. Correct.

        idx_top = self.atm.get_layer_index(71000)
        self.assertEqual(idx_top, 6)

    def test_layer_index_negative(self):
        # Directly call get_layer_index with negative value to hit fallback
        idx = self.atm.get_layer_index(-500.0)
        self.assertEqual(idx, 0)
