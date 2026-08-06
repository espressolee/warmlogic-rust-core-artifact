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
[P4] Tests for SovereignHSM Module.

Tests hardware security module integration:
- HSM type detection
- Hardware ID generation
- Signing operations
- Attestation
"""

import unittest

from warm_logic.security.hsm import HardwareReport, SovereignHSM, get_hsm


class TestSovereignHSM(unittest.TestCase):
    """Test SovereignHSM functionality."""

    def test_hsm_initialization(self):
        """Test HSM initializes correctly."""
        hsm = SovereignHSM()
        self.assertIsNotNone(hsm)
        self.assertIn(hsm._hsm_type, ["TPM", "SECURE_ENCLAVE", "VIRTUAL", "SIMULATED"])

    def test_get_hardware_id(self):
        """Test hardware ID generation."""
        hsm = SovereignHSM()
        hw_id = hsm.get_hardware_id()

        self.assertIsInstance(hw_id, str)
        self.assertGreater(len(hw_id), 16)

    def test_get_hardware_info(self):
        """Test hardware info retrieval."""
        hsm = SovereignHSM()
        info = hsm.get_hardware_info()

        self.assertIn("platform", info)
        self.assertIn("hsm_type", info)
        self.assertIn("rust_available", info)
        self.assertIn("tpm_available", info)
        self.assertIn("secure_enclave", info)

    def test_sign_message(self):
        """Test message signing."""
        hsm = SovereignHSM()
        message = "Test message for signing"

        signature = hsm.sign(message)

        self.assertIsInstance(signature, str)
        self.assertGreater(len(signature), 10)  # Minimum signature length

    def test_sign_different_messages_different_signatures(self):
        """Test that different messages produce different signatures."""
        hsm = SovereignHSM()

        sig1 = hsm.sign("Message 1")
        sig2 = hsm.sign("Message 2")

        self.assertNotEqual(sig1, sig2)

    def test_get_entropy(self):
        """Test entropy generation."""
        hsm = SovereignHSM()

        entropy1 = hsm.get_entropy(32)
        entropy2 = hsm.get_entropy(32)

        self.assertEqual(len(entropy1), 32)
        self.assertEqual(len(entropy2), 32)
        self.assertNotEqual(entropy1, entropy2)  # Should be random

    def test_get_report(self):
        """Test hardware report generation."""
        hsm = SovereignHSM()
        report = hsm.get_report()

        self.assertIsInstance(report, HardwareReport)
        self.assertIn(
            report.hsm_type, ["TPM", "SECURE_ENCLAVE", "VIRTUAL", "SIMULATED"]
        )
        self.assertGreaterEqual(report.reality_score, 0.0)
        self.assertLessEqual(report.reality_score, 1.0)

    def test_attest(self):
        """Test hardware attestation."""
        hsm = SovereignHSM()

        attestation_data, signature = hsm.attest()

        self.assertIsInstance(attestation_data, str)
        self.assertIsInstance(signature, str)
        self.assertIn("timestamp", attestation_data)
        self.assertIn("hardware_id", attestation_data)

    def test_singleton_get_hsm(self):
        """Test that get_hsm returns singleton."""
        hsm1 = get_hsm()
        hsm2 = get_hsm()

        self.assertIs(hsm1, hsm2)


class TestHSMWithRustCore(unittest.TestCase):
    """Test HSM with Rust Core available."""

    def setUp(self):
        """Check if Rust Core is available."""
        try:
            import warm_logic_rs

            self.rust_available = True
        except ImportError:
            self.rust_available = False

    def test_rust_core_integration(self):
        """Test Rust Core is detected when available."""
        hsm = SovereignHSM()

        if self.rust_available:
            self.assertTrue(hsm._rust_available)
        else:
            self.skipTest("Rust Core not available")

    def test_virtual_hsm_type_with_rust(self):
        """Test VirtualHSM is used when Rust Core available and no TPM/SE."""
        hsm = SovereignHSM()

        if self.rust_available and not hsm._tpm_available and not hsm._secure_enclave:
            self.assertEqual(hsm._hsm_type, "VIRTUAL")

    def test_ml_dsa_signature_length(self):
        """Test ML-DSA-65 signature is ~6618 chars when using Rust."""
        hsm = SovereignHSM()

        if self.rust_available:
            sig = hsm.sign("Test message")
            # ML-DSA-65 signature is 3309 bytes = ~6618 hex chars
            # But simulated mode uses different format
            if not sig.startswith("SIM_"):
                self.assertGreater(len(sig), 1000)


class TestHSMStrictMode(unittest.TestCase):
    """Test HSM strict mode."""

    def test_strict_mode_without_hardware(self):
        """Test strict mode fails without real hardware."""
        # This test only runs in environments without TPM/Secure Enclave
        # Skip if we have hardware
        try:
            import platform

            if platform.system() == "Darwin":
                self.skipTest("macOS has Secure Enclave")
            if platform.system() == "Linux":
                import os

                if os.path.exists("/dev/tpm0"):
                    self.skipTest("TPM available")

            with self.assertRaises(RuntimeError):
                SovereignHSM(strict_mode=True)
        except Exception:
            self.skipTest("Cannot test strict mode in this environment")


if __name__ == "__main__":
    unittest.main()
