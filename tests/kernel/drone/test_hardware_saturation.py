"""
Tests for Drone Hardware Abstraction Layer (hardware.py).
Target: 100% Saturation.
"""

import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.drone.hardware import (
    DJIInterface,
    DroneHardwareFactory,
    DroneHardwareInterface,
    DroneProvider,
    DroneTestFramework,
    HardwareConfig,
    PixhawkInterface,
)
from warm_logic.kernel.drone.types import DroneState


class TestHardwareSaturation(unittest.TestCase):
    # --- Factory Tests ---

    def test_factory_create_dji(self):
        config = HardwareConfig(provider=DroneProvider.DJI, connection="usb")
        hw = DroneHardwareFactory.create(config)
        self.assertIsInstance(hw, DJIInterface)
        self.assertEqual(hw.config.connection, "usb")

    def test_factory_create_pixhawk(self):
        config = HardwareConfig(
            provider=DroneProvider.PIXHAWK, connection="/dev/ttyUSB0"
        )
        hw = DroneHardwareFactory.create(config)
        self.assertIsInstance(hw, PixhawkInterface)

    def test_factory_create_px4_ardupilot(self):
        # Verify other aliases map to PixhawkInterface
        for p in [DroneProvider.PX4, DroneProvider.ARDUPILOT]:
            config = HardwareConfig(provider=p, connection="udp:14550")
            hw = DroneHardwareFactory.create(config)
            self.assertIsInstance(hw, PixhawkInterface)

    def test_factory_unknown_provider(self):
        config = HardwareConfig(provider="INVALID", connection="x")
        with self.assertRaises(ValueError):
            DroneHardwareFactory.create(config)

    # --- Pixhawk Interface Tests ---

    def test_pixhawk_lifecycle(self):
        config = HardwareConfig(provider=DroneProvider.PIXHAWK, connection="test")
        hw = PixhawkInterface(config)

        # Initial State
        status = hw.get_status()
        self.assertFalse(status.is_connected)
        self.assertFalse(status.is_armed)
        self.assertEqual(status.state, DroneState.IDLE)

        # Arm Fail (Not Connected)
        res = hw.arm()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_connected")

        # Connect
        self.assertTrue(hw.connect())
        self.assertTrue(hw.get_status().is_connected)

        # Takeoff Fail (Not Armed)
        res = hw.takeoff(10)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_armed")

        # Arm Success
        res = hw.arm()
        self.assertTrue(res["success"])
        self.assertTrue(hw.get_status().is_armed)
        self.assertEqual(hw.get_status().state, DroneState.FLYING)

        # Takeoff Success
        res = hw.takeoff(15.5)
        self.assertTrue(res["success"])
        self.assertEqual(res["altitude"], 15.5)
        self.assertEqual(hw.get_status().position.altitude, 15.5)

        # Land
        res = hw.land()
        self.assertTrue(res["success"])
        self.assertFalse(hw._armed)
        self.assertEqual(hw.get_status().position.altitude, 0)

    # --- DJI Interface Tests ---

    def test_dji_lifecycle(self):
        config = HardwareConfig(provider=DroneProvider.DJI, connection="test")
        hw = DJIInterface(config)

        self.assertTrue(hw.connect())
        self.assertTrue(hw.arm()["success"])
        self.assertTrue(hw.takeoff(20)["success"])

        status = hw.get_status()
        self.assertEqual(status.position.altitude, 20)
        self.assertTrue(status.is_armed)

        self.assertTrue(hw.land()["success"])
        self.assertFalse(hw.get_status().is_armed)

    # --- Abstract Method Coverage ---

    def test_abstract_methods(self):
        """Cover abstract base class methods by calling super()."""

        class ConcreteHardware(DroneHardwareInterface):
            def connect(self) -> bool:
                super().connect()
                return True

            def arm(self):
                super().arm()
                return {}

            def takeoff(self, alt: float):
                super().takeoff(alt)
                return {}

            def land(self):
                super().land()
                return {}

            def get_status(self):
                super().get_status()
                return MagicMock()

        h = ConcreteHardware()
        self.assertTrue(h.connect())
        self.assertEqual(h.arm(), {})
        self.assertEqual(h.takeoff(10), {})
        self.assertEqual(h.land(), {})
        self.assertIsInstance(h.get_status(), MagicMock)

    # --- Framework Tests ---

    def test_test_framework_run(self):
        fw = DroneTestFramework()

        # Create a mock interface that succeeds
        mock_hw = MagicMock(spec=DroneHardwareInterface)
        mock_hw.connect.return_value = True
        mock_hw.arm.return_value = {"success": True}
        mock_hw.takeoff.return_value = {"success": True}
        mock_hw.get_status.return_value = MagicMock()
        mock_hw.land.return_value = {"success": True}

        fw.add_interface("mock_ok", mock_hw)

        # Run
        report = fw.run_all_tests()

        summary = report["summary"]["mock_ok"]
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["passed"], 5)

    def test_test_framework_failures(self):
        fw = DroneTestFramework()

        # Create mock that fails logic
        mock_fail = MagicMock(spec=DroneHardwareInterface)
        # connect returns False -> pass=False (fixed logic)
        mock_fail.connect.return_value = False

        # arm raises exception -> pass=False
        mock_fail.arm.side_effect = Exception("Boom")

        fw.add_interface("mock_fail", mock_fail)
        report = fw.run_all_tests()

        details = report["details"]["mock_fail"]

        # Verify boolean failure
        connect_res = next(d for d in details if d["test"] == "connect")
        self.assertFalse(connect_res["pass"], "Boolean False should be failure")

        # Verify exception failure
        arm_res = next(d for d in details if d["test"] == "arm")
        self.assertFalse(arm_res["pass"], "Exception should be failure")
        self.assertEqual(arm_res["error"], "Boom")
