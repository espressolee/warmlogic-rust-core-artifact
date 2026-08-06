import unittest
from unittest.mock import MagicMock, patch

from src.warm_logic.kernel.sys.cryptography import MLDSA, HardwareEnclave, PQCKeypair


class TestHardwareBoundDID(unittest.TestCase):
    @patch("warm_logic.kernel.rust_loader.load_rust_core")
    def test_key_sealing_unsealing(self, mock_rust):
        """Verify that keys can be sealed and unsealed via the HardwareRealityBinder."""
        mock_core = MagicMock()
        mock_rust.return_value = mock_core

        # Simulated 'seal' returns data prefixed with 'SEALED:'
        mock_core.HardwareRealityBinder.seal_to_silicon.side_effect = lambda d: (
            b"SEALED:" + d
        )
        mock_core.HardwareRealityBinder.unseal_from_silicon.side_effect = lambda d: (
            d[7:] if d.startswith(b"SEALED:") else Exception("Mismatch")
        )

        original_key = b"private_key_material"
        sealed = HardwareEnclave.seal_to_silicon(original_key)
        self.assertTrue(sealed.startswith(b"SEALED:"))

        unsealed = HardwareEnclave.unseal_from_silicon(sealed)
        self.assertEqual(unsealed, original_key)

    @patch("warm_logic.kernel.rust_loader.load_rust_core")
    def test_unseal_failure_on_mismatch(self, mock_rust):
        """Verify that unsealing fails if the hardware doesn't match."""
        mock_core = MagicMock()
        mock_rust.return_value = mock_core

        mock_core.HardwareRealityBinder.unseal_from_silicon.side_effect = Exception(
            "Hardware Mismatch"
        )

        with self.assertRaises(Exception):
            HardwareEnclave.unseal_from_silicon(b"invalid_sealed_data")


if __name__ == "__main__":
    unittest.main()
