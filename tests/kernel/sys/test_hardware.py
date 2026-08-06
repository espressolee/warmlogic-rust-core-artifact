# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic hardware attestation module."""

import hashlib
import os
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.hardware import HardwareAttestor


class TestHardwareAttestor:
    """Test HardwareAttestor class."""

    @patch("warm_logic.kernel.substrate.hardware.SovereignHAL")
    def test_get_hardware_uuid_success(self, mock_hal_class):
        """Successfully retrieves hardware UUID."""
        mock_hal = MagicMock()
        mock_hal.get_silicon_id.return_value = "test-uuid-12345"
        mock_hal_class.return_value = mock_hal

        result = HardwareAttestor.get_hardware_uuid()
        assert result == "test-uuid-12345"
        mock_hal.get_silicon_id.assert_called_once()

    @patch("warm_logic.kernel.substrate.hardware.SovereignHAL")
    def test_get_hardware_uuid_failure(self, mock_hal_class):
        """Raises RuntimeError when hardware ID unavailable."""
        mock_hal = MagicMock()
        mock_hal.get_silicon_id.side_effect = Exception("TPM not available")
        mock_hal_class.return_value = mock_hal

        with pytest.raises(RuntimeError) as exc_info:
            HardwareAttestor.get_hardware_uuid()
        assert "Physical Hardware ID required" in str(exc_info.value)

    @patch.object(HardwareAttestor, "get_hardware_uuid")
    def test_generate_attestation_packet(self, mock_get_uuid):
        """Generates deterministic attestation packet."""
        mock_get_uuid.return_value = "test-uuid-abc"

        packet = HardwareAttestor.generate_attestation_packet()

        # Verify it's a valid SHA256 hash
        assert len(packet) == 64
        assert all(c in "0123456789abcdef" for c in packet)

        # Verify determinism
        packet2 = HardwareAttestor.generate_attestation_packet()
        assert packet == packet2

    @patch.object(HardwareAttestor, "get_hardware_uuid")
    def test_generate_attestation_includes_kernel(self, mock_get_uuid):
        """Attestation packet includes kernel version."""
        mock_get_uuid.return_value = "uuid-123"
        kernel_version = os.uname().release

        # Manually compute expected hash
        raw_token = f"WARM-HW-ROOT|uuid-123|{kernel_version}"
        expected = hashlib.sha256(raw_token.encode()).hexdigest()

        result = HardwareAttestor.generate_attestation_packet()
        assert result == expected

    @patch.object(HardwareAttestor, "generate_attestation_packet")
    def test_verify_attestation_valid(self, mock_gen):
        """Verifies valid attestation."""
        mock_gen.return_value = "abc123def456"

        result = HardwareAttestor.verify_attestation("abc123def456")
        assert result is True

    @patch.object(HardwareAttestor, "generate_attestation_packet")
    def test_verify_attestation_invalid(self, mock_gen):
        """Rejects invalid attestation."""
        mock_gen.return_value = "abc123def456"

        result = HardwareAttestor.verify_attestation("wrong-hash")
        assert result is False

    @patch.object(HardwareAttestor, "generate_attestation_packet")
    def test_verify_attestation_case_sensitive(self, mock_gen):
        """Attestation verification is case-sensitive."""
        mock_gen.return_value = "abc123"

        assert HardwareAttestor.verify_attestation("ABC123") is False
        assert HardwareAttestor.verify_attestation("abc123") is True
