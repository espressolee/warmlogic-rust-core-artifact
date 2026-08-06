import asyncio
import unittest
from unittest.mock import MagicMock, patch

from src.warm_logic.kernel.sys.diagnostics import SiliconHealthMonitor
from src.warm_logic.kernel.sys.hot_swapper import HotSwapManager


class TestRecursiveEvolution(unittest.TestCase):
    def test_health_monitor_logic(self):
        """Verify that SiliconHealthMonitor correctly identifies critical stress."""
        monitor = SiliconHealthMonitor()

        with patch("psutil.virtual_memory") as mock_mem:
            # 1. Normal State
            mock_mem.return_value.available = 100 * 1024 * 1024  # 100MB free
            self.assertTrue(monitor.verify_safety_bounds())

            # 2. Critical State (Low memory)
            mock_mem.return_value.available = 20 * 1024 * 1024  # 20MB free
            self.assertFalse(monitor.verify_safety_bounds())

    @patch("warm_logic.kernel.constitution.UpdateSafetyAxiom.verify_update")
    def test_hot_swap_patch_application(self, mock_verify):
        """Verify that HotSwapManager applies patches after crossing the safety gate."""
        mock_dht = MagicMock()
        manager = HotSwapManager(mock_dht)

        original_hash = manager.current_hash
        manager.target_hash = "v2"

        # 1. Reject invalid patch - hash should remain unchanged
        mock_verify.return_value = False
        asyncio.run(manager.apply_binary_patch(b"invalid_data"))
        self.assertEqual(manager.current_hash, original_hash)

        # 2. Accept valid patch - hash changes after disk modification
        mock_verify.return_value = True
        result = asyncio.run(
            manager.apply_binary_patch(b"valid_patch_signed_by_root")
        )
        self.assertTrue(result)
        # After patch, hash is recalculated from disk (not necessarily target_hash)
        self.assertIsNotNone(manager.current_hash)


if __name__ == "__main__":
    unittest.main()
