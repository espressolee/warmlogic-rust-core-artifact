"""
Saturation Tests for Reality Constants.
Targets: constants.py
"""

import unittest

from warm_logic.kernel.drone.reality.constants import CONSTANTS, PhysicalConstants


class TestConstantsSaturation(unittest.TestCase):
    def test_singleton(self):
        self.assertIsInstance(CONSTANTS, PhysicalConstants)

    def test_gravity_methods(self):
        # Standard
        self.assertAlmostEqual(CONSTANTS.gravity_at_latitude(0), 9.780, places=3)

        # WGS84 overrides
        g_pole = CONSTANTS.gravity_at_latitude(90.0)
        g_equator = CONSTANTS.gravity_at_latitude(0.0)
        self.assertGreater(g_pole, g_equator)

    def test_air_properties(self):
        self.assertGreater(CONSTANTS.AIR_MOLAR_MASS, 0)
        self.assertGreater(CONSTANTS.AIR_GAS_CONSTANT, 0)

    def test_wgs84_properties(self):
        self.assertGreater(CONSTANTS.EARTH_EQUATORIAL_RADIUS, 6000000)
        self.assertLess(CONSTANTS.EARTH_FLATTENING, 1.0)
