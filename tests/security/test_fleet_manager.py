import time
import unittest

from warm_logic.kernel.hardware.confidential import HardwareGuard
from warm_logic.system.fleet.manager import FleetManager, FleetNode


class TestFleetManager(unittest.TestCase):
    def setUp(self):
        self.manager = FleetManager()
        self.report = HardwareGuard.get_hardware_report()

    def test_node_registration(self):
        """Verify that nodes can be registered and their status is VERIFIED."""
        self.manager.register_node("node-1", self.report)
        self.assertEqual(len(self.manager.nodes), 1)
        self.assertEqual(self.manager.nodes["node-1"].status, "VERIFIED")

    def test_fleet_health(self):
        """Verify aggregate health reporting."""
        self.manager.register_node("node-1", self.report)
        health = self.manager.get_fleet_health()
        self.assertTrue(health["healthy"])
        self.assertEqual(health["total_nodes"], 1)

    def test_node_offline(self):
        """Verify that nodes are marked OFFLINE after timeout."""
        self.manager.register_node("node-1", self.report)
        # Mock last_seen to be in the past
        self.manager.nodes["node-1"].last_seen = time.time() - 120
        health = self.manager.get_fleet_health()
        self.assertEqual(health["counts"]["OFFLINE"], 1)
        self.assertFalse(health["healthy"])

    def test_heartbeat_recovery(self):
        """Verify that heartbeats can recover an OFFLINE node."""
        self.manager.register_node("node-1", self.report)
        self.manager.nodes["node-1"].last_seen = time.time() - 120
        self.manager.heartbeat("node-1")
        health = self.manager.get_fleet_health()
        self.assertEqual(health["counts"]["VERIFIED"], 1)
        self.assertTrue(health["healthy"])


if __name__ == "__main__":
    unittest.main()
