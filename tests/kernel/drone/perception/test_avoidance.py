"""
[Phase 140] Tests for Obstacle Avoidance Logic.
"""

import unittest

import numpy as np

from warm_logic.kernel.drone.perception.avoidance import SafetyLevel, SafetyMonitor
from warm_logic.kernel.drone.perception.mapper import OccupancyMapper


class TestAvoidance(unittest.TestCase):
    def setUp(self):
        self.mapper = OccupancyMapper(size_m=20.0, resolution_m=1.0)
        self.monitor = SafetyMonitor(self.mapper)

    def test_safe_path(self):
        """Test that a clear path returns SAFE."""
        pos = np.array([0.0, 0.0, 0.0])
        vel = np.array([5.0, 0.0, 0.0])  # Moving North

        status = self.monitor.check_safety(pos, vel)
        self.assertEqual(status.level, SafetyLevel.SAFE)

    def test_collision_detection(self):
        """Test that an obstacle in path triggers CRITICAL/WARNING."""
        # Place obstacle at 4m North
        # Grid center is 10,10,10. Map is 20m.
        # Pos 0,0,0 is center.
        # North +4m -> (4, 0, 0)

        # Populate grid manually
        # Need to know internal grid mapping or use public API?
        # Mapper has no public 'set_voxel'.
        # But we can update with a fake depth map OR access .grid directly.
        # Direct access for testing is easiest.

        # _ned_to_grid(4, 0, 0)
        ix, iy, iz = self.mapper._ned_to_grid(np.array([4.0, 0.0, 0.0]))
        self.mapper.occupancy[ix, iy, iz] = True

        # Move towards it at 5m/s
        pos = np.array([0.0, 0.0, 0.0])
        vel = np.array([5.0, 0.0, 0.0])

        # Distance is 4m. lookahead 2s.
        # 4m < 5m/s * 2s? Yes.
        # 4m < warning_dist (5m)? Yes.
        # 4m > critical (2m)? Yes.

        status = self.monitor.check_safety(pos, vel)

        # Should be WARNING or CRITICAL depending on thresholds
        # With dist=4m, it should be WARNING.
        self.assertNotEqual(status.level, SafetyLevel.SAFE)

        if status.level == SafetyLevel.WARNING:
            self.assertIsNotNone(status.suggested_velocity)
            # Verify suggested velocity is NOT colliding
            # e.g. rotated
            print(f"Evasive Vel: {status.suggested_velocity}")

    def test_critical_stop(self):
        """Test immediate stop if obstacle is too close."""
        # Obstacle at 1.5m
        ix, iy, iz = self.mapper._ned_to_grid(np.array([1.5, 0.0, 0.0]))
        self.mapper.occupancy[ix, iy, iz] = True

        pos = np.array([0.0, 0.0, 0.0])
        vel = np.array([5.0, 0.0, 0.0])

        # Distance 1.5m < critical (2m)
        status = self.monitor.check_safety(pos, vel)
        self.assertEqual(status.level, SafetyLevel.CRITICAL)
        np.testing.assert_array_equal(status.suggested_velocity, np.zeros(3))
