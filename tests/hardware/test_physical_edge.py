import os
import tempfile
import unittest
from unittest.mock import mock_open, patch

from warm_logic.kernel.mesh.gossip import ThermalThrottler
from warm_logic.kernel.security.silicon import SG2000Binder


class TestPhysicalEdge(unittest.TestCase):
    def test_sg2000_detection(self):
        """Verify SG2000 hardware detection logic."""
        mock_cpuinfo = "Hardware : cv1800b\nSerial : 0000000000000000"

        with patch("builtins.open", mock_open(read_data=mock_cpuinfo)) as m:
            # We must handle multiple open calls because SG2000Binder checks multiple files
            # But python's mock_open is tricky with multiple files.
            # Ideally we patch open just for cpuinfo, or rely on side_effect.

            # Let's use side_effect to serve different content based on filename
            def side_effect(filename, mode="r", *args, **kwargs):
                if filename == "/proc/cpuinfo":
                    return mock_open(read_data=mock_cpuinfo).return_value
                return mock_open(read_data="").return_value

            m.side_effect = side_effect

            fp = SG2000Binder.get_fingerprint()
            # FP is hashed, so we can't see "HW_MODEL" directly in output,
            # but we know if it didn't fail and didn't return VIRTUAL_REALITY fallback (unless strict mode off)

            # Actually, to verify we caught "cv1800b", we can spy on the markers list if it was accessible,
            # Or better, we trust if fp is NOT "VIRTUAL_REALITY" hash.
            # But wait, unless we have rust binder, it might fall back to VR if no markers found?
            # Our code adds markers if cv1800b is found.

            self.assertNotEqual(
                fp, "ed9b31908815152a55855f4639908de75691e847761d7637841103c817293076"
            )  # SHA3-256("VIRTUAL_REALITY")
            print("✅ Verified SG2000 Detection")

    def test_strict_mode_enforcement(self):
        """Verify STRICT_HARDWARE halts on missing hardware."""
        with patch.dict(os.environ, {"STRICT_HARDWARE": "1"}):
            # Raise FileNotFoundError for all open calls to ensure no markers
            with patch("builtins.open", side_effect=FileNotFoundError):
                with self.assertRaisesRegex(RuntimeError, "Hardware Binding Failed"):
                    SG2000Binder.get_fingerprint()
        print("✅ Verified STRICT_HARDWARE enforcement")

    def test_thermal_throttling(self):
        """Verify ThermalThrottler slows gossip on heat."""
        base_interval = 5.0

        # Case 1: Cool (40C) -> 40000 millidegrees
        with patch("builtins.open", mock_open(read_data="40000")):
            with patch("os.path.exists", return_value=True):
                delay = ThermalThrottler.get_gossip_delay(base_interval)
                self.assertEqual(delay, base_interval)

        # Case 2: Hot (80C) -> 80000 millidegrees
        with patch("builtins.open", mock_open(read_data="80000")):
            with patch("os.path.exists", return_value=True):
                delay = ThermalThrottler.get_gossip_delay(base_interval)
                self.assertEqual(delay, base_interval * 4.0)

        print("✅ Verified Thermal Throttling")


if __name__ == "__main__":
    unittest.main()
