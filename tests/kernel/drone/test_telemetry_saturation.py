import json
import socket
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.drone.telemetry import TelemetryManager, TelemetryPacket


class TestTelemetrySaturation(unittest.TestCase):
    def setUp(self):
        self.tm = TelemetryManager("TEST_TELEM_SAT", mode="network")

    def tearDown(self):
        self.tm.close()

    def test_connect_parse(self):
        """L119-128: Verify connect parses host:port."""
        self.tm.connect("192.168.1.100:5000")
        self.assertEqual(self.tm._gs_host, "192.168.1.100")
        self.assertEqual(self.tm._gs_port, 5000)
        self.assertTrue(self.tm._connected)

    def test_blocking_io_error(self):
        """L177-178: Verify BlockingIOError is ignored."""
        if self.tm._sock is not None:
            self.tm._sock.close()
        self.tm._sock = MagicMock()
        self.tm._connected = True
        self.tm._sock.sendto.side_effect = BlockingIOError()

        status = MagicMock()
        status.to_dict.return_value = {}
        # Should not raise
        self.tm.send_status(status)

    def test_verify_packet_logic(self):
        """L189-206: Verify packet signature verification branches."""
        # 1. No signature
        pkt = TelemetryPacket("1", 0, "D1", {}, signature=None)
        self.assertFalse(self.tm.verify_packet(pkt))

        # 2. HMAC Fallback (PQC disabled or key missing)
        self.tm._pqc_enabled = False
        pkt.signature = "invalid_hmac"
        self.assertFalse(self.tm.verify_packet(pkt))

        # Valid HMAC
        # We need to generate a valid HMAC manually or let TM do it?
        # TM only has _sign_packet, which uses current keys.
        # Let's use tm to sign, then verify.
        pkt.signature = self.tm._sign_packet(pkt)
        self.assertTrue(self.tm.verify_packet(pkt))

    @patch("warm_logic.kernel.drone.telemetry.SovereignSecurity", create=True)
    def test_verify_pqc_branches(self, MockSecurity):
        """L194-200: Verify PQC verification success and failure."""
        self.tm._pqc_enabled = True
        self.tm._public_key = "pub_key"  # Expects string
        pkt = TelemetryPacket("1", 0, "D1", {}, signature="pqc_sig")

        # Success
        MockSecurity.verify.return_value = True
        self.assertTrue(self.tm.verify_packet(pkt))

        # Exception during verify -> warning -> return None/False?
        # Code: try... except... logger.warning. Then falls through to HMAC fallback!
        MockSecurity.verify.side_effect = Exception("PQC fail")
        # Fallback to HMAC check logic.
        # Since 'pqc_sig' matches neither PQC nor HMAC, it returns False (likely).
        self.assertFalse(self.tm.verify_packet(pkt))

    def test_check_connection_timeout(self):
        """L210-215: Verify connection health checks."""
        # Not connected
        self.tm._connected = False
        res = self.tm.check_connection()
        self.assertFalse(res["connected"])

        # Connected, timed out
        self.tm._connected = True
        self.tm._last_rx = time.time() - 10.0  # > 5.0 timeout
        res = self.tm.check_connection()
        self.assertFalse(res["connected"])
        self.assertEqual(res["action"], "rtl")

        # Connected, active
        self.tm._last_rx = time.time()
        res = self.tm.check_connection()
        self.assertTrue(res["connected"])

    def test_get_stats_zero_tx(self):
        """L219-222: Verify stats with 0 tx to avoid div errors."""
        self.tm._tx_count = 0
        stats = self.tm.get_stats()
        self.assertEqual(stats["avg_latency_ms"], 0)

    def test_close_socket(self):
        """L240-242: Verify close cleans up socket."""
        if self.tm._sock is not None:
            self.tm._sock.close()
        sock = MagicMock()
        self.tm._sock = sock
        self.tm.close()
        sock.close.assert_called_once()
        self.assertIsNone(self.tm._sock)

    @patch("warm_logic.security.pqc.SovereignSecurity.generate_keypair")
    def test_pqc_init_fail(self, mock_keygen):
        """L96-97: Verify exception during keygen is caught."""
        # We need to force PQC_AVAILABLE = True context
        with patch("warm_logic.kernel.drone.telemetry.PQC_AVAILABLE", True):
            mock_keygen.side_effect = Exception("Keygen Error")
            tm = TelemetryManager("TEST")
            # Should have logged warning and continued
            # PQC enabled should be False (or True but keys None?)
            # Code: self._pqc_enabled = True is AFTER generate_keypair
            # So if exception raises, _pqc_enabled remains False (default).
            self.assertFalse(tm._pqc_enabled)
