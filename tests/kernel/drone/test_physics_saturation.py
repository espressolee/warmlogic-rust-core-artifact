import math
import unittest

from warm_logic.kernel.drone.physics import (
    AStarPathfinder,
    PhysicsState,
    RK4Integrator,
    SpatialIndex,
)
from warm_logic.kernel.drone.types import Position


class TestPhysicsSaturation(unittest.TestCase):
    def test_rk4_low_speed_drag(self):
        """L68-73: Verify drag is zero at very low speeds."""
        rk4 = RK4Integrator()
        # State with nearly zero velocity
        state = PhysicsState(0, 0, 0, 0.001, 0.001, 0.001, 12.0, 1.0)
        # Speed ~0.0017 < 0.01 threshold

        # Thrust 0
        derivs = rk4._derivatives(state, (0, 0, 0))

        # Acceleration should optionally NOT include drag component,
        # or drag is explicitly set to 0.
        # Logic: if speed < 0.01: drag = 0.
        # ax = tx/m. If drag was present, it would be negative.
        # With 0 thrust, ax should be 0.
        self.assertEqual(derivs.vx, 0.0)
        self.assertEqual(derivs.vy, 0.0)
        # vz includes gravity (-9.81)
        self.assertAlmostEqual(derivs.vz, -9.81, places=2)

    def test_astar_timeout_fallback(self):
        """L339/372: Verify A* returns direct path on timeout/cutoff."""
        # Force timeout by setting max_iterations=0
        finder = AStarPathfinder(grid_resolution=10.0)
        start = Position(0, 0, 10)
        goal = Position(100, 100, 10)

        path = finder.find_path(start, goal, max_iterations=0)

        # Should return [start, goal] directly
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0], start)
        self.assertEqual(path[1], goal)

    def test_astar_blocked_fallback(self):
        """L372: Verify A* returns direct path if blocked (and no path found)."""
        finder = AStarPathfinder(grid_resolution=10.0)

        # Create a wall of obstacles
        # 3D grid. Wall at x=50.
        # Min/Max for wall
        finder.add_obstacle(Position(40, -100, 0), Position(60, 200, 100))

        start = Position(0, 0, 10)
        goal = Position(100, 0, 10)

        # Restrict iterations to avoid long search if it tries to go around far away
        # or let it fail if enclosed.
        # With infinite wall (y -100 to 200), if resolution is 10, it effectively blocks direct path.
        # If it returns direct path, it means it gave up.
        # Let's set low iterations to force give-up or ensure it returns fallback
        path = finder.find_path(start, goal, max_iterations=100)

        # If failed, returns [start, goal]
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0], start)
        self.assertEqual(path[1], goal)

    def test_spatial_index_empty_query(self):
        """L413: Verify query on empty/dirty index returns empty list."""
        index = SpatialIndex()
        # Initially empty
        results = index.query(37.0, 127.0)
        self.assertEqual(results, [])

        # Add item, then query
        index.insert(36.0, 126.0, 38.0, 128.0, "data")
        results = index.query(37.0, 127.0)
        self.assertEqual(results, ["data"])

    def test_spatial_index_rebuild_logic(self):
        """L395-402: Verify dirty flag/rebuild logic."""
        index = SpatialIndex()
        self.assertTrue(index._dirty)
        index.insert(0, 0, 1, 1, "A")
        self.assertTrue(index._dirty)

        # Query triggers rebuild
        index.query(0.5, 0.5)
        self.assertFalse(index._dirty)
        self.assertTrue(len(index._sorted_by_lat) > 0)
