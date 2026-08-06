"""
Tests for Drone Control Interface (DroneController).
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.drone.control import DroneController, DroneState, FlightMode
from warm_logic.kernel.drone.types import Position


class TestDroneController(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.drone = DroneController("TEST_DRONE")
        # Mock connection
        self.drone._connected = True
        self.drone._armed = True
        self.drone._state = DroneState.FLYING
        # These tests validate the controller's internal physics path.
        self.drone.use_external_physics = False
        self.drone._battery.reset()

    def test_initialization(self):
        """Verify initial state."""
        d = DroneController()
        self.assertEqual(d._state, DroneState.IDLE)
        self.assertFalse(d._connected)
        self.assertFalse(d._armed)
        self.assertEqual(d._battery.percent, 100.0)

    def test_arm_disarm(self):
        """Verify ARM/DISARM logic."""
        self.drone.disarm()
        self.assertFalse(self.drone._armed)
        self.assertEqual(self.drone._state, DroneState.IDLE)

        res = self.drone.arm()
        self.assertTrue(res["success"])
        self.assertTrue(self.drone._armed)
        self.assertEqual(self.drone._state, DroneState.ARMED)

    def test_takeoff(self):
        """Verify takeoff command."""
        self.drone._state = DroneState.ARMED
        res = self.drone.takeoff(altitude=15.0)

        self.assertTrue(res["success"])
        self.assertEqual(res["target_altitude"], 15.0)
        # Should transition via TAKEOFF -> FLYING (simulated instant in blocking cmd, or immediate state set)
        self.assertEqual(self.drone._state, DroneState.FLYING)

    def test_goto_physics(self):
        """Verify goto sets target for physics engine."""
        target = Position(37.6, 127.0, 50.0)
        res = self.drone.goto(target)

        self.assertTrue(res["success"])
        self.assertIsNotNone(self.drone._target_position)
        self.assertEqual(self.drone._target_position, target)
        self.assertTrue(res["eta_seconds"] > 0)

        # Verify physics step moves drone
        initial_dist = self.drone._position.distance_to(target)
        self.drone.update_physics()
        new_dist = self.drone._position.distance_to(target)
        self.assertTrue(new_dist <= initial_dist)

    def test_emergency_stop(self):
        """Verify emergency stop halts everything."""
        self.drone.goto(Position(37.6, 127.0, 50.0))

        res = self.drone.emergency_stop()
        self.assertTrue(res["success"])
        self.assertEqual(self.drone._state, DroneState.EMERGENCY)
        self.assertFalse(self.drone._armed)
        self.assertIsNone(self.drone._target_position)
        self.assertEqual(self.drone._velocity.speed, 0.0)

    def test_reroute_logic(self):
        """Verify reroute functionality."""
        obs_min = Position(37.55, 126.95, 0)
        obs_max = Position(37.56, 126.96, 100)

        # Determine path around obstacle
        path = self.drone.reroute_around_obstacle(obs_min, obs_max)
        # Even if empty (direct line blocked or not), it should return list
        self.assertIsInstance(path, list)

    def test_battery_drain(self):
        """Verify battery drains during flight."""
        self.drone._state = DroneState.FLYING
        # Simulate high load (climb)
        self.drone._velocity.down = -2.0  # Climbing
        # Set target position so _physics_step doesn't early-return
        self.drone._target_position = Position(37.6, 127.0, 100.0)

        initial = self.drone._battery.percent
        # 60s flight = 600 steps of 0.1s
        # We call internal _physics_step directly to bypass time.time() mocking complexity
        # and dt clamping in update_physics()
        for _ in range(600):
            self.drone._physics_step(0.1)

        self.assertTrue(self.drone._battery.percent < initial)

    async def test_async_goto(self):
        """Verify async blocking goto."""
        # Use close target for speed
        target = Position(0.0001, 0.0, 10.0)  # Very close to home
        res = await self.drone.goto_blocking(target)
        self.assertTrue(res["success"])
        self.assertAlmostEqual(self.drone._position.altitude, 10.0, delta=1.0)
