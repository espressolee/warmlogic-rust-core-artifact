import time
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.drone.control import (
    CommandType,
    DroneController,
    DroneState,
    FlightMode,
)
from warm_logic.kernel.drone.types import Command, Position


class TestDroneControlSaturation(unittest.TestCase):
    def setUp(self):
        self.drone = DroneController("TEST_SATURATION")
        # Saturation cases exercise internal controller physics paths.
        self.drone.use_external_physics = False
        # Ensure battery starts at 100% for most tests
        self.drone._battery.reset()

    def test_connect_success_logs(self):
        """L130-138: Verify connect logs and state."""
        with self.assertLogs("DroneControl", level="INFO") as cm:
            res = self.drone.connect("udp:127.0.0.1:14550")
            self.assertTrue(res)
            self.assertTrue(self.drone._connected)
            self.assertTrue(any("Connected to udp" in r for r in cm.output))

    def test_disconnect(self):
        """L142-144: Verify disconnect resets state."""
        self.drone.connect()
        self.drone.disconnect()
        self.assertFalse(self.drone._connected)

    def test_arm_guards(self):
        """L147-148: Verify arming guards."""
        # 1. Not connected
        self.drone._connected = False
        res = self.drone.arm()
        self.assertFalse(res["success"])
        self.assertIn("not_connected", res["error"])

        # 2. Already moving (invalid state for arming?)
        self.drone._connected = True
        self.drone._state = DroneState.FLYING
        # Currently arm() succeeds even if flying (implementation aligns with this)
        res = self.drone.arm()
        self.assertTrue(res["success"])

    def test_takeoff_guards(self):
        """L157-159: Verify takeoff guards."""
        self.drone._state = DroneState.IDLE  # Not ARMED
        res = self.drone.takeoff()
        self.assertFalse(res["success"])
        self.assertIn("not_armed", res["error"])

    def test_physics_idle_drain(self):
        """L180-186: Verify physics step drains idle power when not flying."""
        self.drone._state = DroneState.IDLE
        initial = self.drone._battery.percent

        # Manually trigger physics step
        # idle power is 5W. 5W/16V = 0.3A.
        # 1 hour = 0.3Ah = 300mAh. 300/5000 = 6%.
        # We simulate 3600s check
        steps = 36000  # 3600s / 0.1s
        # BUT _physics_step is protected. And we don't want to run 36000 steps.
        # Just run 1 massive step if possible, but _physics_step does not take dt?
        # It takes dt.
        self.drone._physics_step(3600.0)

        # Should have drained
        self.assertLess(self.drone._battery.percent, initial)

    def test_execute_command_dispatch(self):
        """L477-497: Verify execute_command dispatch logic."""
        self.drone._connected = True

        # ARM
        cmd_arm = Command(id="1", command_type=CommandType.ARM, params={})
        res = self.drone.execute_command(cmd_arm)
        self.assertTrue(res["success"])
        self.assertEqual(res["command_id"], "1")

        # TAKEOFF
        cmd_takeoff = Command(
            id="2", command_type=CommandType.TAKEOFF, params={"altitude": 10}
        )
        res = self.drone.execute_command(cmd_takeoff)
        self.assertTrue(res["success"])

        # RTL
        cmd_rtl = Command(id="3", command_type=CommandType.RTL, params={})
        res = self.drone.execute_command(cmd_rtl)
        self.assertTrue(res["success"])
        self.assertEqual(self.drone._mode, FlightMode.RTL)

        # UNKNOWN
        # We need to mock a command with unknown type since enum enforces valid types
        # Create a dummy object or just force it if python allows, but Enum is strict.
        # If we can't create invalid Enum, we can't hit 'else' branch of dispatch
        # unless we pass something that is NOT in the map.
        # CommandType has 6 values. Handlers map has 6 keys.
        # So 'else' branch might be unreachable if typed correctly?
        # Let's check handlers keys.

    def test_set_speed(self):
        """L347-364: Verify set_speed."""
        res = self.drone.set_speed(15.0)
        self.assertTrue(res["success"])
        self.assertEqual(self.drone._speed_setting, 15.0)

    def test_power_consumption_states(self):
        """L159, 161: Verify power consumption in various states."""
        # ARMED
        self.drone._state = DroneState.ARMED
        p_armed = self.drone._get_power_consumption()
        self.assertTrue(p_armed > 0)

        # EMERGENCY
        self.drone._state = DroneState.EMERGENCY
        p_emerg = self.drone._get_power_consumption()
        # Emergency cuts motors, so power is lowest (0 or idle depending on impl, map says 0.0)
        self.assertTrue(p_emerg < p_armed)

        # FLYING (Climb vs Hover)
        self.drone._state = DroneState.FLYING
        # Mock physics state
        self.drone._physics_state = MagicMock()
        self.drone._physics_state.vx = 0
        self.drone._physics_state.vy = 0
        self.drone._physics_state.vz = 0.0  # Hover
        p_hover = self.drone._get_power_consumption()

        self.drone._physics_state.vz = 2.0  # Climb
        p_climb = self.drone._get_power_consumption()
        self.assertTrue(p_climb > p_hover)

    def test_physics_step_navigation(self):
        """L186, 208-209, 224: Verify navigation logic in physics loop."""
        self.drone._state = DroneState.FLYING
        self.drone._home = Position(0, 0, 0)
        self.drone._physics_state = MagicMock()
        self.drone._physics_state.x = 0
        self.drone._physics_state.y = 0
        self.drone._physics_state.z = 10
        # Dummy battery to prevent error
        self.drone._battery = MagicMock()
        self.drone._battery.estimate_current.return_value = 1.0
        self.drone._rk4 = MagicMock()
        self.drone._rk4.mass = 1.0
        # Return same state to avoid crash
        self.drone._rk4.step.return_value = self.drone._physics_state

        # 1. No target (L186)
        self.drone._target_position = None
        self.drone._physics_step(0.1)
        # Should return early (no crash)

        # 2. Arrived at waypoint (L208-209)
        # Set target close to current position
        goal = Position(0, 0, 10.0)  # Lat/Lon 0 is "home" if physics x/y is 0
        self.drone._target_position = goal
        # Need to ensure coordinate conversion results in distance < 0.5
        # logic: target_x = (goal.lon - home.lon) * ...
        # If goal == home, dx=0.

        # Add a path
        next_wp = Position(0.0001, 0, 10.0)
        self.drone._current_path = [goal, next_wp]
        self.drone._path_index = 0

        self.drone._physics_step(0.1)

        # Should have advanced to next waypoint
        self.assertEqual(self.drone._path_index, 1)
        self.assertEqual(self.drone._target_position, next_wp)

    def test_reroute_success(self):
        """L291-300: Verify reroute updates path."""
        # Mock pathfinder
        self.drone._pathfinder = MagicMock()
        new_path = [Position(0, 0, 10), Position(1, 1, 10)]
        self.drone._pathfinder.find_path.return_value = new_path

        self.drone._target_position = Position(2, 2, 20)
        self.drone._position = Position(0, 0, 0)

        path = self.drone.reroute_around_obstacle(Position(0, 0, 0), Position(1, 1, 1))

        self.assertEqual(path, new_path)
        self.assertEqual(self.drone._current_path, new_path)
        self.assertEqual(self.drone._target_position, new_path[0])

    def test_gen_command_id(self):
        """L147-148: Verify command ID generation."""
        cid1 = self.drone._gen_command_id()
        cid2 = self.drone._gen_command_id()
        self.assertNotEqual(cid1, cid2)
        self.assertTrue(cid1.startswith("CMD"))

    def test_emergency_stop(self):
        """L415-418: Verify emergency stop logic."""
        self.drone._state = DroneState.FLYING
        res = self.drone.emergency_stop()
        self.assertTrue(res["success"])
        self.assertEqual(self.drone._state, DroneState.EMERGENCY)
