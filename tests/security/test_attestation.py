import os
import unittest
from unittest.mock import patch

from warm_logic.kernel.hardware.confidential import (
    HardwareGuard,
    enforce_hardware_lock,
)


class TestAttestation(unittest.TestCase):
    @patch("warm_logic.kernel.rust_loader.load_rust_core")
    def test_hardware_fallback(self, mock_load):
        """Ensure system halts if Rust core is missing (simulated failure)."""
        print("\nTesting Hardware Fallback...")
        # Force Rust Core to fail loading to test the fallback logic
        mock_load.side_effect = RuntimeError("Mocked Rust Load Failure")

        with self.assertRaises(SystemError) as cm:
            enforce_hardware_lock()

        self.assertIn("CRITICAL: Physical Security Violation", str(cm.exception))
        print("✅ Hardware Lock Enforcement Verified.")

    @patch(
        "warm_logic.kernel.hardware.confidential.HardwareGuard.verify_system_integrity"
    )
    def test_mock_enclave_success(self, mock_verify):
        """Simulate a successful enclave report."""
        print("Testing Mock Enclave Success...")
        mock_verify.return_value = (True, "SECURE_ENCLAVE_SIGNED")

        # Should not raise exception
        enforce_hardware_lock()
        print("✅ Mock Enclave Pass Verified.")


if __name__ == "__main__":
    unittest.main()
