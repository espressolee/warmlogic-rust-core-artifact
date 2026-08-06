"""
[Phase 150] Saturation tests for MAVLink bridge behavior.
Target: 100% Saturation.
"""

import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

# Crucially, we must ensure 'mavutil' is mocked before MavlinkBridge is even imported
# if we want to avoid issues with module-level imports in the bridge.
mock_mavutil = MagicMock()
mock_mavutil.mavlink = MagicMock()
sys.modules["pymavlink"] = mock_mavutil

from warm_logic.kernel.drone.hardware import DroneProvider, HardwareConfig
from warm_logic.kernel.drone.mavlink_bridge import MavlinkBridge
from warm_logic.kernel.drone.types import DroneState


class TestMavlinkBridgeSaturation(unittest.TestCase):
    def setUp(self):
        # Patching at the level where it's used in the bridge
        self.patcher = patch(
            "warm_logic.kernel.drone.mavlink_bridge.mavutil", mock_mavutil.mavlink
        )
        self.mock_mavutil_in_bridge = self.patcher.start()

        # Reset side effects and return values for every test
        self.mock_mavutil_in_bridge.mavlink_connection.side_effect = None
        self.mock_mavutil_in_bridge.mavlink_connection.return_value = MagicMock()

        self.config = HardwareConfig(
            provider=DroneProvider.MAVLINK,
            connection="udp:127.0.0.1:14550",
            baud_rate=57600,
        )
        self.bridge = MavlinkBridge(self.config)

    def tearDown(self):
        self.patcher.stop()
        if self.bridge._thread and self.bridge._thread.is_alive():
            self.bridge._stop_event.set()
            self.bridge._thread.join(timeout=0.1)

    def test_connect_success(self):
        mock_master = MagicMock()
        self.mock_mavutil_in_bridge.mavlink_connection.return_value = mock_master

        # Prevent the listener thread from actually running for long
        self.bridge._stop_event.set()

        success = self.bridge.connect()
        self.assertTrue(success)
        mock_master.wait_heartbeat.assert_called_once()
        mock_master.mav.request_data_stream_send.assert_called()

    def test_connect_failure(self):
        self.mock_mavutil_in_bridge.mavlink_connection.side_effect = Exception(
            "Conn Error"
        )
        success = self.bridge.connect()
        self.assertFalse(success)
        # Reset side effect for subsequent tests
        self.mock_mavutil_in_bridge.mavlink_connection.side_effect = None

    def test_handle_messages(self):
        mock_msg = MagicMock()

        # HEARTBEAT
        mock_msg.get_type.return_value = "HEARTBEAT"
        mock_msg.base_mode = 0x80
        self.mock_mavutil_in_bridge.mavlink.MAV_MODE_FLAG_SAFETY_ARMED = 0x80
        self.bridge._handle_message(mock_msg)
        self.assertTrue(self.bridge._armed)

        # GLOBAL_POSITION_INT
        mock_msg.get_type.return_value = "GLOBAL_POSITION_INT"
        mock_msg.lat = 375665000
        mock_msg.lon = 1269780000
        mock_msg.relative_alt = 10000
        mock_msg.vx = 100
        mock_msg.vy = 200
        mock_msg.vz = 300
        self.bridge._handle_message(mock_msg)
        self.assertEqual(self.bridge._position.latitude, 0.0)
        self.assertEqual(self.bridge._velocity.north, 1.0)

        # ATTITUDE
        mock_msg.get_type.return_value = "ATTITUDE"
        mock_msg.roll = 0.1
        mock_msg.pitch = 0.2
        mock_msg.yaw = 0.3
        self.bridge._handle_message(mock_msg)
        self.assertEqual(self.bridge._attitude.roll, 0.1)

        # SYS_STATUS
        mock_msg.get_type.return_value = "SYS_STATUS"
        mock_msg.voltage_battery = 12000
        mock_msg.current_battery = 500
        mock_msg.battery_remaining = 80
        self.bridge._handle_message(mock_msg)
        self.assertEqual(self.bridge._battery_voltage, 12.0)
        self.assertEqual(self.bridge._battery_remaining, 80)

        # GPS_RAW_INT
        mock_msg.get_type.return_value = "GPS_RAW_INT"
        mock_msg.satellites_visible = 12
        self.bridge._handle_message(mock_msg)
        self.assertEqual(self.bridge._satellites_visible, 12)

    def test_commands_success(self):
        self.bridge._connected = True
        self.bridge._master = MagicMock()
        self.bridge._master.mode_mapping.return_value = {"GUIDED": 4, "LAND": 9}

        # arm
        res = self.bridge.arm()
        self.assertTrue(res["success"])
        self.bridge._master.arducopter_arm.assert_called_once()
        self.bridge._master.motors_armed_wait.assert_called_once()

        # takeoff
        res = self.bridge.takeoff(10.0)
        self.assertTrue(res["success"])
        self.bridge._master.mav.command_long_send.assert_called()

        # land
        res = self.bridge.land()
        self.assertTrue(res["success"])

    def test_commands_no_connection(self):
        self.bridge._connected = False
        self.assertFalse(self.bridge.arm()["success"])
        self.assertFalse(self.bridge.takeoff(10.0)["success"])
        self.assertFalse(self.bridge.land()["success"])

    def test_commands_exception(self):
        self.bridge._connected = True
        self.bridge._master = MagicMock()
        self.bridge._master.mode_mapping.return_value = {"GUIDED": 4, "LAND": 9}

        # arm exception
        self.bridge._master.arducopter_arm.side_effect = Exception("Arm Error")
        res = self.bridge.arm()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "Arm Error")
        self.bridge._master.arducopter_arm.side_effect = None

        # takeoff failure (set_mode fails)
        with patch.object(self.bridge, "set_mode", return_value=False):
            res = self.bridge.takeoff(10.0)
            self.assertFalse(res["success"])
            self.assertEqual(res["error"], "failed_to_enter_guided_mode")

        # takeoff exception
        self.bridge._master.mav.command_long_send.side_effect = Exception(
            "Takeoff Error"
        )
        res = self.bridge.takeoff(10.0)
        self.assertFalse(res["success"])
        self.bridge._master.mav.command_long_send.side_effect = None

        # land failure (set_mode fails)
        with patch.object(self.bridge, "set_mode", return_value=False):
            res = self.bridge.land()
            self.assertFalse(res["success"])
            self.assertEqual(res["error"], "failed_to_enter_land_mode")

        # land exception
        self.bridge._master.set_mode.side_effect = Exception("Land Error")
        res = self.bridge.land()
        self.assertFalse(res["success"])
        self.bridge._master.set_mode.side_effect = None

    def test_set_mode_logic(self):
        self.bridge._master = MagicMock()
        self.bridge._master.mode_mapping.return_value = {"GUIDED": 4}

        # Success
        self.assertTrue(self.bridge.set_mode("GUIDED"))

        # Unknown mode
        self.assertFalse(self.bridge.set_mode("UNKNOWN"))

        # Exception
        self.bridge._master.set_mode.side_effect = Exception("SetMode Error")
        self.assertFalse(self.bridge.set_mode("GUIDED"))

        # No master
        self.bridge._master = None
        self.assertFalse(self.bridge.set_mode("GUIDED"))

    def test_get_status(self):
        self.bridge._connected = True
        self.bridge._armed = True
        self.bridge._battery_remaining = 75
        self.bridge._satellites_visible = 12
        status = self.bridge.get_status()
        self.assertTrue(status.is_connected)
        self.assertEqual(status.state, DroneState.FLYING)
        self.assertEqual(status.battery_percent, 75.0)
        self.assertEqual(status.gps_satellites, 12)

        self.bridge._connected = False
        status = self.bridge.get_status()
        self.assertFalse(status.is_connected)
        self.assertEqual(status.state, DroneState.IDLE)

    def test_listener_loop_edge_cases(self):
        self.bridge._master = MagicMock()
        # recv_match returns None then raises Exception
        self.bridge._master.recv_match.side_effect = [None, Exception("Stream Error")]

        # Trigger manually to avoid thread complexity
        self.bridge._stop_event.set()
        import time

        with patch("time.sleep"):
            self.bridge._listener_loop()
        # Should complete without crashing

    def test_request_data_stream_edge_cases(self):
        self.bridge._master = None
        self.bridge._request_data_stream()  # Should return immediately

    def test_mavlink_import_failure(self):
        # We need to test the case where mavutil is None
        # Since it's already imported at module level in this test, we might need a fresh bridge
        # or mock the module-level 'mavutil' within the bridge module.
        with patch("warm_logic.kernel.drone.mavlink_bridge.mavutil", None):
            bridge = MavlinkBridge(self.config)
            self.assertFalse(bridge.connect())


if __name__ == "__main__":
    unittest.main()
