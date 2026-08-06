"""
Unit tests for MavlinkBridge.
Mocks pymavlink to verify logic without hardware.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock pymavlink before importing bridge
sys.modules["pymavlink"] = MagicMock()
sys.modules["pymavlink.mavutil"] = MagicMock()

from warm_logic.kernel.drone.hardware import DroneProvider, HardwareConfig
from warm_logic.kernel.drone.mavlink_bridge import MavlinkBridge


class TestMavlinkBridge(unittest.TestCase):
    def setUp(self):
        self.config = HardwareConfig(
            provider=DroneProvider.MAVLINK, connection="udp:localhost:14550"
        )
        self.bridge = MavlinkBridge(self.config)

        # Mock the master connection
        self.mock_master = MagicMock()
        self.mock_master.target_system = 1
        self.mock_master.target_component = 1

        # Inject mock master
        self.bridge._master = self.mock_master
        self.bridge._connected = True

    def test_connect_success(self):
        # Reset bridge to unconnected
        self.bridge._connected = False
        self.bridge._master = None

        with patch("warm_logic.kernel.drone.mavlink_bridge.mavutil") as mock_mavutil:
            mock_mavutil.mavlink_connection.return_value = self.mock_master

            success = self.bridge.connect()

            self.assertTrue(success)
            self.assertTrue(self.bridge._connected)
            mock_mavutil.mavlink_connection.assert_called_once()
            self.mock_master.wait_heartbeat.assert_called_once()

    def test_arm_command(self):
        self.bridge.arm()
        self.mock_master.arducopter_arm.assert_called_once()
        self.mock_master.motors_armed_wait.assert_called_once()

    def test_takeoff_command(self):
        # Mock mode mapping
        self.mock_master.mode_mapping.return_value = {"GUIDED": 4}

        result = self.bridge.takeoff(10.0)

        self.assertTrue(result["success"])
        # Check set mode called
        self.mock_master.set_mode.assert_called_with(4)
        # Check command long sent
        self.mock_master.mav.command_long_send.assert_called()

    def test_telemetry_parsing_global_position(self):
        # Simulate GLOBAL_POSITION_INT message
        msg = MagicMock()
        msg.get_type.return_value = "GLOBAL_POSITION_INT"
        msg.lat = 375000000  # 37.5 deg
        msg.lon = 1270000000  # 127.0 deg
        msg.relative_alt = 10000  # 10m
        msg.vx = 100  # 1m/s
        msg.vy = 0
        msg.vz = -50  # 0.5m/s climb

        self.bridge._handle_message(msg)

        pos = self.bridge._position
        self.assertAlmostEqual(pos.latitude, 37.5)
        self.assertAlmostEqual(pos.longitude, 127.0)
        self.assertAlmostEqual(pos.altitude, 10.0)

        vel = self.bridge._velocity
        self.assertAlmostEqual(vel.north, 1.0)
        self.assertAlmostEqual(vel.down, -0.5)

    def test_telemetry_parsing_attitude(self):
        msg = MagicMock()
        msg.get_type.return_value = "ATTITUDE"
        msg.roll = 0.1
        msg.pitch = -0.1
        msg.yaw = 1.57

        self.bridge._handle_message(msg)

        att = self.bridge._attitude
        self.assertAlmostEqual(att.roll, 0.1)
        self.assertAlmostEqual(att.yaw, 1.57)


if __name__ == "__main__":
    unittest.main()
