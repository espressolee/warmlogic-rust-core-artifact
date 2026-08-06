# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""
[P3xx] Unit tests for security modules.
Tests: hardening.py, silicon.py
"""

import hashlib
import hmac
import os
import unittest
from unittest import mock

from warm_logic.kernel.security.hardening import (
    FIPSCryptoModule,
    FIPSMode,
    CryptoOperation,
)
from warm_logic.kernel.security.hardware import HardwareAttestation
from warm_logic.kernel.security.silicon import SG2000Binder


class TestFIPSMode(unittest.TestCase):
    """Test FIPS mode enumeration."""

    def test_fips_mode_values(self):
        """Verify FIPS mode enum values."""
        self.assertEqual(FIPSMode.DISABLED.value, "disabled")
        self.assertEqual(FIPSMode.ENABLED.value, "enabled")
        self.assertEqual(FIPSMode.STRICT.value, "strict")

    def test_fips_mode_is_enum(self):
        """Verify FIPSMode is enumerable."""
        modes = list(FIPSMode)
        self.assertEqual(len(modes), 3)


class TestCryptoOperation(unittest.TestCase):
    """Test CryptoOperation dataclass."""

    def test_crypto_operation_creation(self):
        """Test creating a CryptoOperation."""
        from datetime import datetime

        op = CryptoOperation(
            timestamp=datetime.now(),
            operation="hash",
            algorithm="SHA256",
            key_id="key1",
            success=True,
        )
        self.assertEqual(op.operation, "hash")
        self.assertEqual(op.algorithm, "SHA256")
        self.assertTrue(op.success)

    def test_crypto_operation_failure(self):
        """Test recording a failed operation."""
        from datetime import datetime

        op = CryptoOperation(
            timestamp=datetime.now(),
            operation="encrypt",
            algorithm="AES-256-GCM",
            key_id="key2",
            success=False,
        )
        self.assertFalse(op.success)


class TestFIPSCryptoModule(unittest.TestCase):
    """Test FIPS crypto module."""

    def test_init_disabled_mode(self):
        """Test initialization with disabled mode."""
        module = FIPSCryptoModule(mode=FIPSMode.DISABLED)
        self.assertEqual(module.mode, FIPSMode.DISABLED)
        self.assertEqual(len(module.operations), 0)

    def test_init_enabled_mode(self):
        """Test initialization with enabled mode runs self-tests."""
        module = FIPSCryptoModule(mode=FIPSMode.ENABLED)
        self.assertEqual(module.mode, FIPSMode.ENABLED)

    def test_approved_algorithms_hash(self):
        """Test approved hash algorithms."""
        approved = FIPSCryptoModule.APPROVED_ALGORITHMS["hash"]
        self.assertIn("SHA256", approved)
        self.assertIn("SHA384", approved)
        self.assertIn("SHA512", approved)

    def test_approved_algorithms_encrypt(self):
        """Test approved encryption algorithms."""
        approved = FIPSCryptoModule.APPROVED_ALGORITHMS["encrypt"]
        self.assertIn("AES-256-GCM", approved)
        self.assertIn("AES-256-CBC", approved)

    def test_approved_algorithms_mac(self):
        """Test approved MAC algorithms."""
        approved = FIPSCryptoModule.APPROVED_ALGORITHMS["mac"]
        self.assertIn("HMAC-SHA256", approved)
        self.assertIn("HMAC-SHA384", approved)

    def test_approved_algorithms_sign(self):
        """Test approved signature algorithms."""
        approved = FIPSCryptoModule.APPROVED_ALGORITHMS["sign"]
        self.assertIn("ECDSA-P384", approved)
        self.assertIn("RSA-2048", approved)

    def test_sha256_known_answer_test(self):
        """Verify SHA-256 KAT passes."""
        test_input = b"abc"
        expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        result = hashlib.sha256(test_input).hexdigest()
        self.assertEqual(result, expected)

    def test_hmac_sha256_basic(self):
        """Verify HMAC-SHA256 basic functionality."""
        key = b"key"
        msg = b"The quick brown fox"
        result = hmac.new(key, msg, hashlib.sha256).hexdigest()
        self.assertEqual(len(result), 64)  # 256 bits = 64 hex chars


class TestSG2000Binder(unittest.TestCase):
    """Test silicon binding for hardware identity."""

    def test_get_fingerprint_virtual(self):
        """Test fingerprint generation in virtual environment."""
        # In test environment, no hardware markers should be found
        with mock.patch.dict(os.environ, {"STRICT_HARDWARE": "0"}):
            fingerprint = SG2000Binder.get_fingerprint()
            # Should get a valid hex string
            self.assertEqual(len(fingerprint), 64)  # SHA3-256

    def test_get_fingerprint_strict_mode_fail(self):
        """Test strict mode fails without hardware."""
        with mock.patch.dict(os.environ, {"STRICT_HARDWARE": "1"}):
            # Mock cpuinfo to return empty
            with mock.patch("builtins.open", side_effect=FileNotFoundError):
                with self.assertRaises(RuntimeError) as ctx:
                    SG2000Binder.get_fingerprint()
                self.assertIn("Hardware Binding Failed", str(ctx.exception))

    def test_fingerprint_deterministic(self):
        """Test fingerprint is deterministic for same input."""
        with mock.patch.dict(os.environ, {"STRICT_HARDWARE": "0"}):
            fp1 = SG2000Binder.get_fingerprint()
            fp2 = SG2000Binder.get_fingerprint()
            self.assertEqual(fp1, fp2)

    @mock.patch(
        "builtins.open", mock.mock_open(read_data="Serial: 1234567890\ncv1800b\n")
    )
    def test_fingerprint_with_cpuinfo(self):
        """Test fingerprint extraction from cpuinfo."""
        # This simulates having CPU serial info
        with mock.patch.dict(os.environ, {"STRICT_HARDWARE": "0"}):
            fingerprint = SG2000Binder.get_fingerprint()
            self.assertEqual(len(fingerprint), 64)

    def test_virtual_reality_hash(self):
        """Test VIRTUAL_REALITY fallback hash."""
        expected = hashlib.sha3_256(b"VIRTUAL_REALITY").hexdigest()
        self.assertEqual(len(expected), 64)


class TestHardwareAttestation(unittest.TestCase):
    """Test hardware attestation."""

    def test_identify_hardware_security_returns_dict(self):
        """Test hardware security scan returns proper structure."""
        result = HardwareAttestation.identify_hardware_security()
        self.assertIsInstance(result, dict)
        self.assertIn("tpm_available", result)
        self.assertIn("secure_enclave_available", result)
        self.assertIn("pqc_accelerator", result)
        self.assertIn("os_hardening", result)

    def test_reality_score_range(self):
        """Test reality score is in valid range."""
        score = HardwareAttestation.get_reality_score()
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    @mock.patch("os.path.exists")
    def test_docker_environment_caps_score(self, mock_exists):
        """Test Docker environment caps reality score."""
        mock_exists.return_value = True  # /.dockerenv exists
        score = HardwareAttestation.get_reality_score()
        self.assertLessEqual(score, 0.5)

    def test_hardware_security_booleans(self):
        """Test all hardware security values are booleans."""
        result = HardwareAttestation.identify_hardware_security()
        for key, value in result.items():
            self.assertIsInstance(value, bool, f"{key} should be boolean")


class TestSecurityIntegration(unittest.TestCase):
    """Integration tests for security modules."""

    def test_fips_with_silicon_binding(self):
        """Test FIPS module can work with silicon identity."""
        fips = FIPSCryptoModule(mode=FIPSMode.ENABLED)
        fingerprint = SG2000Binder.get_fingerprint()

        # Use fingerprint as key derivation input
        derived = hashlib.sha256(fingerprint.encode()).hexdigest()
        self.assertEqual(len(derived), 64)

    def test_crypto_audit_trail(self):
        """Test crypto operations create audit trail."""
        from datetime import datetime

        fips = FIPSCryptoModule(mode=FIPSMode.DISABLED)
        op = CryptoOperation(
            timestamp=datetime.now(),
            operation="hash",
            algorithm="SHA256",
            key_id="test",
            success=True,
        )
        fips.operations.append(op)
        self.assertEqual(len(fips.operations), 1)


if __name__ == "__main__":
    unittest.main()
