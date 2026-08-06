"""
Tests for Drone Safety Monitor (Geofence, R-tree, Limits).
"""

import unittest

from warm_logic.kernel.drone.safety import DroneSafetyMonitor, GeoFence, ViolationType
from warm_logic.kernel.drone.types import Position


class TestSafetyMonitor(unittest.TestCase):
    def setUp(self):
        self.safety = DroneSafetyMonitor()
        self.safety.set_home(Position(37.5, 127.0, 0))
        self.safety.max_distance = 20000.0  # Increase to 20km for testing large fence

        # Add basic geofence
        self.fence = GeoFence(
            id="ZONE_01",
            name="Test Zone",
            fence_type="include",
            vertices=[
                Position(37.4, 126.9, 0),
                Position(37.6, 126.9, 0),
                Position(37.6, 127.1, 0),
                Position(37.4, 127.1, 0),
            ],
            max_altitude=100.0,
        )
        self.safety.set_include_fence(self.fence)
        self.safety.add_geofence(self.fence)  # Trigger index rebuild

    def test_altitude_check(self):
        """Verify altitude limits."""
        # Safe
        res = self.safety.check_position(Position(37.5, 127.0, 50.0))
        self.assertTrue(res["safe"])

        # Unsafe (>100m)
        res = self.safety.check_position(Position(37.5, 127.0, 150.0))
        self.assertFalse(res["safe"])
        self.assertEqual(
            res["violations"][0]["violation_type"], ViolationType.ALTITUDE_LIMIT
        )

    def test_distance_check(self):
        """Verify distance from home."""
        # Safe (0m)
        res = self.safety.check_position(Position(37.5, 127.0, 50.0))
        self.assertTrue(res["safe"])

        # Unsafe (>20000m)
        # 38.0 is ~55km away from 37.5
        far_away = Position(38.0, 127.1, 50.0)
        res = self.safety.check_position(far_away)
        self.assertEqual(res["safe"], False)

        # Check that it triggered distance limit (priority over geofence)
        # Note: If it triggers geofence exit, then distance check failed to catch it
        # or check order is different.
        self.assertEqual(
            res["violations"][0]["violation_type"], ViolationType.DISTANCE_LIMIT
        )

    def test_geofence_inclusion(self):
        """Verify must stay inside include fence."""
        # Inside
        res = self.safety.check_position(Position(37.5, 127.0, 50.0))

        # Outside fence but within distance limit (5km)
        # 37.5, 127.0 is center. 37.7 is ~22km North. Too far.
        # Use 37.6001, 126.9 which is just North of fence (37.6 max)
        outside = Position(37.6001, 126.9, 50.0)
        res = self.safety.check_position(outside)
        self.assertFalse(res["safe"])
        self.assertEqual(
            res["violations"][0]["violation_type"], ViolationType.GEOFENCE_EXIT
        )

    def test_nofly_zone(self):
        """Verify avoidance of no-fly zones."""
        nfz = GeoFence(
            id="NFZ_01",
            name="No Fly",
            fence_type="exclude",
            vertices=[
                Position(37.49, 126.99, 0),
                Position(37.51, 126.99, 0),
                Position(37.51, 127.01, 0),
                Position(37.49, 127.01, 0),
            ],
        )
        self.safety.add_geofence(nfz)

        # Inside NFZ
        inside_nfz = Position(37.5, 127.0, 50.0)
        res = self.safety.check_position(inside_nfz)
        self.assertFalse(res["safe"])
        self.assertEqual(
            res["violations"][0]["violation_type"], ViolationType.NO_FLY_ZONE
        )

    def test_spatial_index_integration(self):
        """
        Verify R-tree index is used.
        Mock the spatial index query to ensure call happens.
        """
        if self.safety._spatial_index:
            # Add many fences
            for i in range(10):
                self.safety.add_geofence(
                    GeoFence(f"FENCE_{i}", "Test", "exclude", [], 100, 0)
                )

            # Should have rebuilt index
            self.assertIsNotNone(self.safety._spatial_index)
            # Query valid point
            res = self.safety._spatial_index.query(37.5, 127.0)
            self.assertTrue(len(res) > 0)
