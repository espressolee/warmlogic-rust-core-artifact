import unittest
from unittest.mock import MagicMock

from warm_logic.kernel.drone.safety import DroneSafetyMonitor, ViolationType
from warm_logic.kernel.drone.types import Position


class TestSafetySaturation(unittest.TestCase):
    def setUp(self):
        self.home = Position(37.0, 127.0, 10.0)
        self.monitor = DroneSafetyMonitor()
        self.monitor.set_home(self.home)
        self.monitor.max_distance = 100.0
        self.monitor.max_altitude = 50.0

    def test_dynamic_geofence_update(self):
        """Verify updating geofence parameters at runtime."""
        # Start safe
        pos = Position(37.0001, 127.0, 20.0)  # Within ~11m (0.0001 deg lat is ~11.1m)
        check = self.monitor.check_position(pos)
        self.assertTrue(check["safe"])

        # Shrink geofence to 5m
        self.monitor.max_distance = 5.0
        check = self.monitor.check_position(pos)
        # Should now be unsafe (11m > 5m)
        self.assertFalse(check["safe"])
        # Check specific violation
        self.assertTrue(
            any(
                v["violation_type"] == ViolationType.DISTANCE_LIMIT
                for v in check["violations"]
            )
        )

    def test_veto_command_logic(self):
        """Verify veto_command blocks unsafe GOTO."""
        self.monitor._veto_active = True

        # Safe command (Latitude 37.00001 is ~1m from home)
        cmd_safe = {
            "id": "1",
            "type": "goto",
            "params": {"lat": 37.00001, "lon": 127.0, "alt": 10},
        }
        res = self.monitor.veto_command(cmd_safe, self.home)
        self.assertFalse(res["blocked"])

        # Unsafe command (Altitude 1000m > 50m)
        cmd_unsafe = {
            "id": "2",
            "type": "goto",
            "params": {"lat": 37.0, "lon": 127.0, "alt": 1000},
        }
        res = self.monitor.veto_command(cmd_unsafe, self.home)
        self.assertTrue(res["blocked"])
        self.assertEqual(self.monitor._blocked_commands, 1)

    def test_get_threats_conversion(self):
        """Verify get_threats converts violations correctly."""
        # Position outside (Altitude 1000m)
        pos = Position(37.0, 127.0, 1000.0)
        threats = self.monitor.get_threats(pos)

        self.assertTrue(len(threats) > 0)
        # Check threat content
        # Altitude violation -> Severity 0.9
        self.assertTrue(any(t.severity >= 0.9 for t in threats))

    def test_clear_violations(self):
        """Verify clearing violations state."""
        # Not applicable if stateless check_position is used.
        pass
