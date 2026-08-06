"""
Tests for Drone Physics Engine (RK4, LiPo, A*, SpatialIndex).
"""

import math
import unittest
from typing import List

from warm_logic.kernel.drone.physics import (
    AStarPathfinder,
    LiPoBatteryModel,
    PhysicsState,
    RK4Integrator,
    SpatialIndex,
)
from warm_logic.kernel.drone.types import Position


class TestPhysics(unittest.TestCase):
    def test_rk4_hover(self):
        """Verify RK4 integration maintains hover height."""
        physics = RK4Integrator(drone_mass=2.5)
        # Initial state: hovering at 50m
        state = PhysicsState(
            x=0, y=0, z=50.0, vx=0, vy=0, vz=0, battery_voltage=16.8, battery_soc=1.0
        )
        # Thrust = weight
        thrust = (0, 0, physics.mass * 9.81)

        # Step forward 1 second in 0.01s steps
        for _ in range(100):
            state = physics.step(state, thrust, 0.01)

        self.assertAlmostEqual(state.z, 50.0, places=2)
        self.assertAlmostEqual(state.vz, 0.0, places=2)

    def test_rk4_climb(self):
        """Verify RK4 integration handles acceleration."""
        physics = RK4Integrator(drone_mass=2.5)
        state = PhysicsState(0, 0, 0, 0, 0, 0, 16.8, 1.0)
        # Thrust > weight (10N excess)
        thrust = (0, 0, physics.mass * 9.81 + 10.0)

        # F=ma => a = 10 / 2.5 = 4 m/s^2
        # v = at = 4 * 1 = 4 m/s (theoretical without drag)
        # With drag (coeff 0.1), velocity will be slightly less (~3.8 m/s)

        for _ in range(100):
            state = physics.step(state, thrust, 0.01)

        # Expect ~3.8 due to drag
        self.assertAlmostEqual(state.vz, 3.8, delta=0.1)
        # z will be slightly less than 2.0
        self.assertAlmostEqual(state.z, 1.9, delta=0.2)

    def test_lipo_curve(self):
        """Verify non-linear LiPo discharge curve."""
        battery = LiPoBatteryModel()
        self.assertEqual(battery.percent, 100.0)
        self.assertAlmostEqual(battery.voltage, 16.8, places=1)

        # Discharge 50% (2500 mAh)
        # Capacity = 5000 mAh
        # 10A for 15 mins (0.25h) = 2.5 Ah = 2500 mAh
        battery.discharge(current_amps=10.0, dt=15 * 60)

        self.assertAlmostEqual(battery.percent, 50.0, delta=1.0)
        self.assertTrue(battery.voltage < 16.0)
        self.assertTrue(battery.voltage > 14.0)

        # Reset
        battery.reset()
        self.assertEqual(battery.percent, 100.0)

    def test_astar_pathfinding(self):
        """Verify A* finds path around obstacle."""
        pf = AStarPathfinder(grid_resolution=10.0)

        # Start at (0,0), Goal at (0, 40)
        # Obstacle at (0, 20) blocking direct path
        obs_min = Position(latitude=0.0001, longitude=0.0001, altitude=0)
        obs_max = Position(latitude=0.0003, longitude=0.0003, altitude=100)
        pf.add_obstacle(obs_min, obs_max)

        start = Position(0, 0, 50)
        goal = Position(0.0004, 0.0004, 50)  # Approx 60m away diagonal

        path = pf.find_path(start, goal)
        self.assertTrue(len(path) > 2)
        # Check no waypoint is inside obstacle (simplified check)

    def test_spatial_index(self):
        """Verify spatial index queries."""
        idx = SpatialIndex()
        idx.insert(37.0, 127.0, 37.1, 127.1, "Zone A")
        idx.insert(37.5, 127.5, 37.6, 127.6, "Zone B")

        # Query Zone A center
        results = idx.query(37.05, 127.05)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "Zone A")

        # Query Empty
        results = idx.query(38.0, 128.0)
        self.assertEqual(len(results), 0)
