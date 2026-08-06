"""
Tests for Drone Telemetry (PQC, Signatures, Network).
"""

import json
import unittest
from datetime import datetime

from warm_logic.kernel.drone.telemetry import TelemetryManager, TelemetryPacket
from warm_logic.kernel.drone.types import (
    Attitude,
    DroneState,
    DroneStatus,
    FlightMode,
    Position,
    Velocity,
)


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        self.tm = TelemetryManager("TEST_TELEM", mode="simulation")
        self.status = DroneStatus(
            timestamp=datetime.now(),
            state=DroneState.FLYING,
            mode=FlightMode.GUIDED,
            position=Position(37.5, 127.0, 50.0),
            velocity=Velocity(0, 0, 0),
            attitude=Attitude(0, 0, 0),
            battery_percent=80.0,
            gps_satellites=12,
            is_armed=True,
            is_connected=True,
            errors=[],
        )

    def test_pqc_enabled(self):
        """Verify PQC is enabled if available."""
        # This depends on environment, but we can check the flag matches key presence
        has_keys = self.tm.public_key is not None
        self.assertEqual(self.tm._pqc_enabled, has_keys)

    def test_packet_creation(self):
        """Verify packet structure."""
        pkt = self.tm.send_status(self.status)
        self.assertIsInstance(pkt, TelemetryPacket)
        self.assertTrue(pkt.encrypted)
        self.assertIsNotNone(pkt.signature)
        self.assertIsNotNone(pkt.nonce)

    def test_signature_verification(self):
        """Verify signature validity."""
        pkt = self.tm.send_status(self.status)

        # Should verify correctly
        self.assertTrue(self.tm.verify_packet(pkt))

        # Tamper with data
        pkt.data["battery_percent"] = 0.0
        # Should fail verification (canonical string mismatch)
        self.assertFalse(self.tm.verify_packet(pkt))

    def test_replay_protection(self):
        """Verify nonce creates unique signatures."""
        pkt1 = self.tm.send_status(self.status)
        pkt2 = self.tm.send_status(self.status)

        self.assertNotEqual(pkt1.nonce, pkt2.nonce)
        self.assertNotEqual(pkt1.signature, pkt2.signature)

    def test_serialization(self):
        """Verify JSON serialization."""
        pkt = self.tm.send_status(self.status)
        data_bytes = pkt.to_bytes()

        # Decode back
        decoded = json.loads(data_bytes.decode("utf-8"))
        self.assertEqual(decoded["id"], pkt.id)
        self.assertEqual(decoded["sig"], pkt.signature)
