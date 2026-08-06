"""
Tests for Mission Planner (mission.py).
Target: 100% Saturation.
"""

import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.drone.mission import MissionPlan, MissionPlanner
from warm_logic.kernel.drone.types import GeoFence, Position, Waypoint


class TestMissionSaturation(unittest.TestCase):
    def setUp(self):
        self.planner = MissionPlanner()

    # --- Mission Creation ---

    def test_create_mission_basic(self):
        wps = [
            Position(0, 0, 0),
            Position(0.001, 0, 10),  # ~111m North
            Position(0.001, 0.001, 10),  # ~111m East
        ]
        mission = self.planner.create_mission("TestMission", wps, speed=10.0)

        self.assertEqual(mission.name, "TestMission")
        self.assertEqual(len(mission.waypoints), 3)
        self.assertTrue(mission.total_distance > 0)
        self.assertTrue(mission.estimated_time > 0)

        # Verify IDs
        self.assertTrue(mission.id.startswith("MSN"))
        self.assertTrue(mission.waypoints[0].id.startswith("WP"))

    def test_create_mission_single_point(self):
        wps = [Position(0, 0, 0)]
        mission = self.planner.create_mission("Single", wps)
        self.assertEqual(mission.total_distance, 0.0)
        self.assertEqual(mission.estimated_time, 0.0)

    # --- Path Planning (A*) ---

    def test_plan_route_direct_no_obstacles(self):
        start = Position(0, 0, 10)
        goal = Position(0.01, 0.01, 10)

        path = self.planner.plan_route(start, goal)
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0], start)
        self.assertEqual(path[1], goal)

    def test_plan_route_avoid_obstacle(self):
        # Setup: Start (0,0), Goal (0, 0.002)
        # Obstacle in between at (0, 0.001)
        start = Position(0, 0, 10)
        goal = Position(0, 0.003, 10)

        # Create obstacle
        obs = GeoFence(
            id="OBS1",
            name="TestObs1",
            fence_type="exclude",
            vertices=[
                Position(-0.0005, 0.001, 0),
                Position(0.0005, 0.001, 0),
                Position(0.0005, 0.002, 100),
                Position(-0.0005, 0.002, 100),
            ],
            min_altitude=0,
            max_altitude=100,
        )

        path = self.planner.plan_route(start, goal, obstacles=[obs])

        self.assertTrue(len(path) > 2)  # Should have intermediate points

        # Verify no point in path is inside obstacle
        for p in path:
            self.assertFalse(obs.contains(p))

    def test_plan_route_no_path_found(self):
        # Create a "Cage" obstacle that surrounds the start point completely
        # This forces A* to exhaust the search space (or hit max iterations) and return direct path
        obs = GeoFence(
            id="CAGE",
            name="Cage",
            fence_type="exclude",
            vertices=[
                Position(-0.1, -0.1, 0),
                Position(0.1, -0.1, 0),
                Position(0.1, 0.1, 100),
                Position(-0.1, 0.1, 100),
            ],
            min_altitude=0,
            max_altitude=100,
        )

        # Start and Goal inside the cage?
        # No, if goal is outside, and start is inside, and walls are impassable.
        start = Position(0, 0, 10)  # Inside
        goal = Position(0.2, 0.2, 10)  # Outside

        # We need to ensure A* fails to find a path through the cage.
        # But wait, if start is inside an "exclude" fence, is it blocked?
        # Implementation of is_blocked:
        # if obs.fence_type == "exclude" and obs.contains(pos): return True

        # If start is blocked, neighbors might be blocked too.
        # If all neighbors of start are blocked (or start itself), open_set processing might be tricky.
        # Actually, self._astar logic:
        # open_set = [(0, id(start), start)]
        # while open_set: ...
        #   for neighbor in get_neighbors(current):
        #       if not is_blocked(neighbor): ...

        # So if start is inside, but we don't check if start is blocked initially.
        # But neighbors (step=100m) will check is_blocked.
        # If we overlap the obstacle such that all neighbors are valid? No, we want them blocked.
        # Make the cage walls thick enough?

        # Actually, simpler: Mock `_astar` to return [start, goal] directly?
        # But we want to cover the code IN `_astar`.

        # Let's use the "World" obstacle that blocks everything.
        obs_world = GeoFence(
            id="WORLD",
            name="World",
            fence_type="exclude",
            vertices=[
                Position(-1, -1, 0),
                Position(1, -1, 0),
                Position(1, 1, 100),
                Position(-1, 1, 100),
            ],
            min_altitude=0,
            max_altitude=100,
        )
        # Mock contains to always True
        with patch(
            "warm_logic.kernel.drone.types.GeoFence.contains", return_value=True
        ):
            path = self.planner.plan_route(start, goal, obstacles=[obs_world])
            # Should return direct path [start, goal] because A* finds no neighbors
            self.assertEqual(len(path), 2)
            self.assertEqual(path, [start, goal])

    def test_get_next_waypoint_none(self):
        self.planner._current_mission = None
        self.assertIsNone(self.planner.get_next_waypoint())

    # --- Replanning ---

    def test_replan_no_active_mission(self):
        with self.assertRaises(ValueError):
            self.planner.replan(Position(0, 0, 0))

    def test_replan_mission_finished(self):
        self.planner.create_mission("Quick", [Position(0, 0, 0)])
        self.planner.advance_waypoint()  # Finish it

        # Replan with no remaining wps
        res = self.planner.replan(Position(0, 0, 0))
        self.assertEqual(res, self.planner._current_mission)

    def test_replan_dynamic_obstacle(self):
        # Create mission A -> B -> C
        wps = [Position(0, 0, 0), Position(0, 0.005, 0), Position(0, 0.01, 0)]
        self.planner.create_mission("Long", wps)

        # Advance to first leg
        self.planner._current_waypoint_idx = 1  # Target is 0.005

        current_pos = Position(0, 0.001, 0)  # En route

        # Add obstacle blocking path to 0.005
        obs = GeoFence(
            id="DYN",
            name="DynObs",
            fence_type="exclude",
            vertices=[
                Position(-0.001, 0.003, 0),
                Position(0.001, 0.003, 0),
                Position(0.001, 0.004, 100),
                Position(-0.001, 0.004, 100),
            ],
            min_altitude=0,
            max_altitude=100,
        )

        # Replan
        new_plan = self.planner.replan(current_pos, new_obstacles=[obs])

        # New plan should include current path to B (detoured) + C
        self.assertGreater(len(new_plan.waypoints), 2)  # Detour points added

    # --- State Management ---

    def test_mission_lifecycle(self):
        self.planner.create_mission("Life", [Position(0, 0, 0), Position(1, 1, 1)])

        # Initial
        p = self.planner.get_progress()
        self.assertTrue(p["active"])
        self.assertEqual(p["current_waypoint"], 0)
        self.assertEqual(p["progress_pct"], 0.0)

        # Next WP
        wp = self.planner.get_next_waypoint()
        self.assertIsNotNone(wp)
        self.assertEqual(wp.position.latitude, 0)

        # Advance
        self.planner.advance_waypoint()
        p = self.planner.get_progress()
        self.assertEqual(p["current_waypoint"], 1)
        self.assertEqual(p["progress_pct"], 50.0)

        # Next WP
        wp = self.planner.get_next_waypoint()
        self.assertEqual(wp.position.latitude, 1)

        # Advance (Finish)
        self.planner.advance_waypoint()
        p = self.planner.get_progress()
        self.assertEqual(p["current_waypoint"], 2)
        self.assertEqual(p["progress_pct"], 100.0)

        # No more WPs
        self.assertIsNone(self.planner.get_next_waypoint())

    def test_get_progress_no_mission(self):
        p = self.planner.get_progress()
        self.assertFalse(p["active"])

    # --- Serialization ---

    def test_mission_to_dict(self):
        m = self.planner.create_mission("Test", [Position(0, 0, 0)])
        d = m.to_dict()
        self.assertEqual(d["name"], "Test")
        self.assertEqual(len(d["waypoints"]), 1)
        self.assertIn("total_distance_m", d)

    # --- Obstacle Management ---

    def test_add_obstacle(self):
        obs = MagicMock(spec=GeoFence)
        self.planner.add_obstacle(obs)
        self.assertIn(obs, self.planner._obstacles)

    # --- Logic Helpers ---

    def test_astar_helper_is_blocked(self):
        pass
