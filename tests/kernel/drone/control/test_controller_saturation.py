"""
Tests for DroneController (controller.py).
Target: 100% Saturation (Unified v10).
"""

import asyncio
import math
import time
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.drone.control.controller import (
    CommandType,
    DroneController,
    FailsafeState,
)
from warm_logic.kernel.drone.types import Command, DroneState, Position


class TestControllerSaturation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.controller = DroneController(drone_id="TEST_DRONE")
        self.controller.connect()
        # Saturation tests for `_physics_step` must exercise the internal integrator.
        self.controller.use_external_physics = False

    # -------------------------------------------------------------------------
    # 1. POWER & PHYSICS
    # -------------------------------------------------------------------------

    def test_power_consumption_modes(self):
        self.controller._state = DroneState.IDLE
        self.assertEqual(self.controller._get_power_consumption(), 5.0)
        self.controller._state = DroneState.ARMED
        self.assertEqual(self.controller._get_power_consumption(), 10.0)
        self.controller._state = DroneState.EMERGENCY
        self.assertEqual(self.controller._get_power_consumption(), 0.0)

        self.controller._state = DroneState.FLYING
        # Climb
        self.controller._physics_state.vz = 2.0
        self.assertEqual(self.controller._get_power_consumption(), 400.0)
        # Flight
        self.controller._physics_state.vz = 0.0
        self.controller._physics_state.vx = 2.0
        self.assertEqual(self.controller._get_power_consumption(), 300.0)
        # Hover
        self.controller._physics_state.vx = 0.0
        self.controller._physics_state.vy = 0.0
        self.assertEqual(self.controller._get_power_consumption(), 200.0)

    def test_physics_step_drain_only(self):
        self.controller._state = DroneState.IDLE
        initial_batt = self.controller._battery.percent
        self.controller._physics_step(1.0)
        self.assertLess(self.controller._battery.percent, initial_batt)

    def test_physics_step_no_target(self):
        self.controller._state = DroneState.FLYING
        self.controller._target_position = None
        self.controller._physics_step(0.01)

    def test_physics_step_path_arrival(self):
        self.controller._state = DroneState.FLYING
        wp1 = Position(0.0666, 0.0781, 10.0)
        self.controller._target_position = wp1
        self.controller._current_path = [wp1]

        # Place drone AT waypoint
        self.controller._physics_state.y = (wp1.latitude - 0.0) * 110540
        self.controller._physics_state.x = (
            (wp1.longitude - 0.0) * 111320 * math.cos(math.radians(0.0))
        )
        self.controller._physics_state.z = 10.0

        self.controller._physics_step(0.01)
        self.assertIsNone(self.controller._target_position)

    def test_physics_step_multipoint_arrival(self):
        self.controller._state = DroneState.FLYING
        wp1 = Position(40, 40, 10.0)
        wp2 = Position(41, 41, 10.0)
        self.controller._current_path = [wp1, wp2]
        self.controller._target_position = wp1
        self.controller._path_index = 0

        # Place drone AT wp1
        self.controller._physics_state.y = (wp1.latitude - 0.0) * 110540
        self.controller._physics_state.x = (
            (wp1.longitude - 0.0) * 111320 * math.cos(math.radians(0.0))
        )
        self.controller._physics_state.z = 10.0

        self.controller._physics_step(0.01)
        self.assertEqual(self.controller._target_position, wp2)

    def test_physics_zero_distance_else(self):
        """Cover the else block when distance <= 0"""
        self.controller._state = DroneState.FLYING
        self.controller._target_position = Position(0.0, 0.0, 0.0)  # Home
        self.controller._physics_state.x = 0
        self.controller._physics_state.y = 0
        self.controller._physics_state.z = 0

        # This effectively makes distance 0
        self.controller._physics_step(0.01)
        # Should finish arrival or stay put.
        # Ensure it didn't crash div by zero.

    # -------------------------------------------------------------------------
    # 2. SENSOR FUSION
    # -------------------------------------------------------------------------

    def test_gps_update_block(self):
        """Directly target the 'if gps_pos:' block."""
        sensors = {
            "gps_pos": (0.0666, 0.0781, 50.0),
            "gps_vel": (1.0, 2.0, 3.0),
            "imu_accel": (0.01, 0.02, -9.8),
            "battery_soc": 0.88,
        }
        self.controller._velocity_d = 0.0
        self.controller.update_state_from_sensors(sensors)
        self.assertEqual(self.controller._velocity_d, 3.0)
        self.assertAlmostEqual(self.controller._position.latitude, 0.0666)

    # -------------------------------------------------------------------------
    # 3. COMMAND DISPATCH
    # -------------------------------------------------------------------------

    def test_command_dispatch_coverage(self):
        """Hit every dictionary entry in execute_command with correct state."""
        # 1. Arm
        self.controller.execute_command(
            Command(id="C1", command_type=CommandType.ARM, params={})
        )

        # 2. Takeoff (Needs Arm)
        self.controller.execute_command(
            Command(id="C2", command_type=CommandType.TAKEOFF, params={"altitude": 50})
        )

        # 3. Goto (Needs Flying)
        self.controller._state = DroneState.FLYING
        self.controller.execute_command(
            Command(
                id="C3",
                command_type=CommandType.GOTO,
                params={
                    "position": {"latitude": 10, "longitude": 20, "altitude": 30},
                    "speed": 15,
                },
            )
        )

        # 4. Set Speed
        self.controller.execute_command(
            Command(id="C4", command_type=CommandType.SET_SPEED, params={"speed": 12})
        )

        # 5. Set Mode
        self.controller.execute_command(
            Command(
                id="C5", command_type=CommandType.SET_MODE, params={"mode": "guided"}
            )
        )

        # 6. Land
        self.controller.execute_command(
            Command(id="C6", command_type=CommandType.LAND, params={})
        )

        # 7. Disarm (Last)
        self.controller.execute_command(
            Command(id="C7", command_type=CommandType.DISARM, params={})
        )

        # 8. Emergency Stop (Anytime)
        self.controller.execute_command(
            Command(id="C8", command_type=CommandType.EMERGENCY_STOP, params={})
        )

        # 9. RTL
        self.controller.execute_command(
            Command(id="C9", command_type=CommandType.RTL, params={})
        )

    def test_execute_unknown_command(self):
        cmd = MagicMock()
        cmd.command_type.value = "MAGIC_FLIP"
        cmd.id = "UNK"
        res = self.controller.execute_command(cmd)
        self.assertFalse(res["success"])
        self.assertIn("unknown_command", res["error"])

    # -------------------------------------------------------------------------
    # 4. FAILSAFES
    # -------------------------------------------------------------------------

    def test_failsafe_triggers_isolated(self):
        # Battery Critical
        self.controller._failsafe_state = FailsafeState.NORMAL
        self.controller._battery._soc = 0.04
        self.controller._check_failsafes()
        self.assertEqual(self.controller._failsafe_state, FailsafeState.LANDING)

        # Battery Low
        self.controller._failsafe_state = FailsafeState.NORMAL
        self.controller._battery._soc = 0.15
        self.controller._check_failsafes()
        self.assertEqual(self.controller._failsafe_state, FailsafeState.RTL)

        # Geofence
        self.controller._failsafe_state = FailsafeState.NORMAL
        self.controller._battery._soc = 1.0
        self.controller._geofence_limit_alt = 10
        self.controller._position = Position(0, 0, 100)
        self.controller._check_failsafes()
        # Geofence RTL enforcement enabled in Phase 200
        self.assertEqual(self.controller._failsafe_state, FailsafeState.RTL)

        # Heartbeat
        self.controller._failsafe_state = FailsafeState.NORMAL
        self.controller._battery._soc = 1.0
        self.controller._position = Position(0.0, 0.0, 0.0)  # Reset to Home
        self.controller._geofence_limit_alt = 100  # Reset limit
        self.controller._last_heartbeat = time.time() - 100
        self.controller._check_failsafes()
        self.assertEqual(self.controller._failsafe_state, FailsafeState.RTL)

    def test_failsafe_overrides_full(self):
        self.controller._armed = True
        self.controller._state = DroneState.FLYING
        # Exercise Python failsafe branch directly; Rust backend returns early.
        self.controller._rust_controller = None

        # RTL
        self.controller._failsafe_state = FailsafeState.RTL
        self.controller.get_control_output()
        self.assertEqual(self.controller._target_position.altitude, 20.0)

        # Landing (w/ target)
        self.controller._failsafe_state = FailsafeState.LANDING
        self.controller._target_position = Position(0, 0, 100)
        self.controller.get_control_output()
        self.assertEqual(self.controller._target_position.altitude, 0.0)

        # Landing (w/o target)
        self.controller._target_position = None
        self.controller.get_control_output()
        self.assertEqual(self.controller._target_position.altitude, 0.0)

    # -------------------------------------------------------------------------
    # 5. ERROR PATHS & MISSING BRANCHES
    # -------------------------------------------------------------------------

    def test_get_control_output_unarmed(self):
        self.controller._armed = False
        res = self.controller.get_control_output()
        self.assertEqual(res, (0, 0, 0, 0))

        self.controller._armed = True
        self.controller._state = DroneState.EMERGENCY
        res = self.controller.get_control_output()
        self.assertEqual(res, (0, 0, 0, 0))

    async def test_goto_blocking_success(self):
        self.controller.arm()
        self.controller._state = DroneState.FLYING
        # Mock goto to verify we call it, but let logic flow
        with patch.object(self.controller, "goto") as mock_goto:
            mock_goto.return_value = {
                "success": True,
                "eta_seconds": 0.1,
                "distance": 10.0,
                "latency_ms": 1.0,
                "physics": "RK4",
            }

            # Create a task to simulate arrival by clearing target
            async def arrive():
                await asyncio.sleep(0.01)
                self.controller._target_position = None

            self.controller._target_position = Position(1, 1, 1)
            asyncio.create_task(arrive())

            res = await self.controller.goto_blocking(Position(1, 1, 1))
            self.assertTrue(res["success"])

    def test_arm_error(self):
        self.controller.disconnect()
        res = self.controller.arm()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_connected")

    def test_takeoff_error(self):
        self.controller.connect()
        self.controller._armed = False
        res = self.controller.takeoff()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_armed")

    def test_goto_error_not_flying(self):
        self.controller.connect()
        self.controller._state = DroneState.IDLE
        res = self.controller.goto(Position(0, 0, 10))
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_flying")

    async def test_goto_blocking_errors(self):
        # 1. goto failure
        with patch.object(self.controller, "goto", return_value={"success": False}):
            res = await self.controller.goto_blocking(Position(0, 0, 0))
            self.assertFalse(res["success"])

        # 2. timeout
        self.controller.arm()
        self.controller._state = DroneState.FLYING
        with patch.object(
            self.controller,
            "goto",
            return_value={"success": True, "eta_seconds": -1, "distance": 1},
        ):
            self.controller._target_position = Position(1, 1, 1)
            res = await self.controller.goto_blocking(Position(1, 1, 1))
            self.assertFalse(res["success"])
            self.assertEqual(res["error"], "timeout")

    # -------------------------------------------------------------------------
    # 6. HELPERS & REROUTE
    # -------------------------------------------------------------------------

    def test_helpers_check_connection(self):
        # Success
        self.controller._connected = True
        self.controller._last_heartbeat = time.time()
        self.assertTrue(self.controller.check_connection())
        # Failure (Timeout)
        self.controller._last_heartbeat = time.time() - 100
        self.assertFalse(self.controller.check_connection())
        # Failure (Disconnect)
        self.controller.disconnect()
        self.assertFalse(self.controller.check_connection())

    def test_reroute_logic(self):
        self.controller._target_position = None
        res = self.controller.reroute_around_obstacle(None, None)
        self.assertEqual(res, [])
        self.controller._target_position = Position(0, 0, 0)
        with patch.object(
            self.controller._pathfinder, "find_path", return_value=[Position(1, 1, 1)]
        ):
            res = self.controller.reroute_around_obstacle(None, None)
            self.assertEqual(len(res), 1)

    def test_helpers_misc(self):
        self.controller.get_status()
        self.controller.send_heartbeat()
        self.controller._gen_command_id()
        self.assertFalse(self.controller.is_moving())

    def test_get_rotation_matrix(self):
        # Trigger explicit coverage for new EKF method
        R = self.controller._ekf.get_rotation_matrix()
        self.assertEqual(R.shape, (3, 3))
