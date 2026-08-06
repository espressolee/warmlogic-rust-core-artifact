import unittest
from unittest.mock import mock_open, patch

from src.warm_logic.kernel.security.silicon import SG2000Binder


class TestSiliconBinding(unittest.TestCase):
    def test_fingerprint_generation_simulation(self):
        """Verify fingerprint generation in simulation mode (no hardware markers)."""
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=IOError):
                fp = SG2000Binder.get_fingerprint()
                # Should match a known fallback or at least be a valid hex sha3
                self.assertEqual(len(fp), 64)

    def test_fingerprint_stability(self):
        """Verify that identical markers produce identical fingerprints."""
        mock_data = {
            "/proc/cpuinfo": "Serial : 00000000abcdef12\n",
            "/sys/class/block/mmcblk0/device/cid": "1234567890\n",
            "/sys/class/net/eth0/address": "aa:bb:cc:dd:ee:ff\n",
            "/etc/machine-id": "machine123\n",
        }

        def side_effect(path, *args, **kwargs):
            if path in mock_data:
                return mock_open(read_data=mock_data[path]).return_value
            raise IOError

        with patch("builtins.open", side_effect=side_effect):
            with patch("os.path.exists", side_effect=lambda p: p in mock_data):
                fp1 = SG2000Binder.get_fingerprint()
                fp2 = SG2000Binder.get_fingerprint()
                self.assertEqual(fp1, fp2)
                self.assertNotEqual(fp1, "VIRTUAL_REALITY")

    def test_verification_logic(self):
        """Verify the identity verification method."""
        with patch.object(SG2000Binder, "get_fingerprint", return_value="stable_fp"):
            self.assertTrue(SG2000Binder.verify_reality("stable_fp"))
            self.assertFalse(SG2000Binder.verify_reality("fake_fp"))


if __name__ == "__main__":
    unittest.main()
