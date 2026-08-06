"""
[Phase 140] Tests for Occupancy Mapper.
"""

import unittest

import numpy as np

from warm_logic.kernel.drone.perception.mapper import OccupancyMapper


class TestMapper(unittest.TestCase):
    def setUp(self):
        # 20m grid with 1m resolution
        self.mapper = OccupancyMapper(size_m=20.0, resolution_m=1.0)

    def test_grid_initialization(self):
        self.assertEqual(self.mapper.grid.shape, (20, 20, 20))
        self.assertFalse(np.any(self.mapper.occupancy))

    def test_ned_to_grid_conversion(self):
        # Center of grid should be (10, 10, 10)
        ix, iy, iz = self.mapper._ned_to_grid(np.array([0.0, 0.0, 0.0]))
        self.assertEqual((ix, iy, iz), (10, 10, 10))

        # Point at N=5, E=-5, D=0
        ix, iy, iz = self.mapper._ned_to_grid(np.array([5.0, -5.0, 0.0]))
        self.assertEqual((ix, iy, iz), (15, 5, 10))

    def test_update_from_depth(self):
        # Fake depth map: a 10x10 wall at 5m distance
        depth_map = np.full((10, 10), 5.0)
        # Drone at origin, facing forward (0,0,0)
        pos = np.array([0.0, 0.0, 0.0])
        attitude = np.array([0.0, 0.0, 0.0])

        # Update multiple times to trigger occupancy threshold (> 2.0)
        for _ in range(3):
            self.mapper.update(depth_map, pos, attitude)

        # Check if point at (5, 0, 0) in NED is occupied
        # Actually center pixel (5,5) projects to N=5 (Forward)
        self.assertTrue(self.mapper.is_occupied(np.array([5.0, 0.0, 0.0])))

        # Far away point should NOT be occupied
        self.assertFalse(self.mapper.is_occupied(np.array([15.0, 0.0, 0.0])))


if __name__ == "__main__":
    unittest.main()
