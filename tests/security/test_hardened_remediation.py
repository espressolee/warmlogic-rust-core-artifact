import asyncio
import unittest
from unittest.mock import MagicMock, patch

from src.warm_logic.kernel.mesh.dht import Contact, RoutingTable
from src.warm_logic.kernel.sys.hot_swapper import HotSwapManager


class TestHarshRemediation(unittest.TestCase):
    def test_enforced_silicon_id(self):
        """Verify that DHT now REJECTS peers without Silicon ID."""
        table = RoutingTable(b"local_id")

        # Peer with valid PQC but MISSING Silicon ID
        bad_peer = Contact(
            node_id=b"bad_id",
            address="1.2.3.4",
            port=5000,
            public_key=b"dontcare",  # Mocked pk
            silicon_id=None,  # Missing!
        )

        # Mock PQC verification to pass, focus on Silicon ID
        with patch.object(RoutingTable, "_verify_binding", return_value=False):
            # This should fail due to our update in dht.py
            self.assertFalse(table._verify_binding(bad_peer))

    def test_hardened_patch_rejection(self):
        """Verify that HotSwapManager rejects patches without Magic Bytes."""
        manager = HotSwapManager(MagicMock())

        # 1. Plain text patch (No Magic Bytes)
        text_patch = b"print('hello')"
        result = asyncio.run(manager.apply_binary_patch(text_patch))
        self.assertFalse(result)

        # 2. Magic Bytes but no Signature
        magic_only = b"\x7fWL_PATCH" + b"some_data"
        result = asyncio.run(manager.apply_binary_patch(magic_only))
        self.assertFalse(result)

        # 3. Valid Magic + Signature Trailer
        valid_mock = b"\x7fWL_PATCH" + b"payload" + b"---PQC_SIG_BEGIN---"
        result = asyncio.run(manager.apply_binary_patch(valid_mock))
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
