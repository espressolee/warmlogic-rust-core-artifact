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
import unittest
from unittest.mock import MagicMock, patch


class TestDHTSaturation(unittest.IsolatedAsyncioTestCase):
    """
    Perfection Saturation for DHT (Mesh).
    Targets Rust fallback and error edges.
    """

    def setUp(self):
        pass

    @patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False)
    async def test_rust_import_failure_fallback(self):
        """Cover lines 40-41: Verify fallback when Rust is missing."""
        from warm_logic.kernel.mesh.dht import SovereignDHT

        dht = SovereignDHT(b"node_id", "127.0.0.1", 9999)
        self.assertFalse(dht.routing._use_rust)
        self.assertTrue(len(dht.routing.buckets) == 1)

    @patch("warm_logic.kernel.mesh.dht.RoutingTable._verify_binding", return_value=True)
    async def test_rust_delegation(self, mock_verify):
        # Line 24-26, 50-51: Rust delegation
        from warm_logic.kernel.mesh.dht import Contact, SovereignDHT

        dht = SovereignDHT(b"node_id", "127.0.0.1", 9999)
        dht.routing._use_rust = True
        dht.routing._rust_table = MagicMock()

        c = Contact(b"other", "1.1.1.1", 80, public_key=b"pk")
        await dht.routing.update(c)  # update is async
        dht.routing._rust_table.update.assert_called()

        dht.routing.find_neighbors(b"target")
        dht.routing._rust_table.find_closest.assert_called()

    @patch("warm_logic.kernel.mesh.dht.RoutingTable._verify_binding", return_value=True)
    async def test_python_bucket_split(self, mock_verify):
        # Line 70-74, 121-122: Bucket split logic
        import hashlib

        from warm_logic.kernel.mesh.dht import K_PARAM, Contact, SovereignDHT

        dht = SovereignDHT(b"\x00" * 32, "127.0.0.1", 9999)
        dht.routing._use_rust = False

        # Fill bucket 0
        for i in range(K_PARAM):
            pk = f"node_pk_{i}".encode()
            cid = hashlib.sha256(pk).digest()
            await dht.routing.update(
                Contact(cid, "1.1.1.1", 80, public_key=pk)
            )  # await async

        # This update should trigger split because local_id is in bucket 0 range
        pk_last = b"last_node"
        cid_last = hashlib.sha256(pk_last).digest()
        await dht.routing.update(
            Contact(cid_last, "2.2.2.2", 80, public_key=pk_last)
        )  # await async
        self.assertTrue(len(dht.routing.buckets) > 1)

    def test_find_node_extra(self):
        # Line 169-173: find_node fallback
        from warm_logic.kernel.mesh.dht import SovereignDHT

        dht = SovereignDHT(b"node_id", "127.0.0.1", 9999)
        dht.routing._use_rust = False
        res = dht.find_node(b"target")
        self.assertIsInstance(res, list)

    def test_store_value_edge(self):
        """Cover lines 199, 205, 209: store_value edges."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            from warm_logic.kernel.mesh.dht import SovereignDHT

            dht = SovereignDHT(b"node_id", "127.0.0.1", 9999)

            # Store value
            dht.store(b"key", "val")
            self.assertEqual(dht.storage[b"key".hex()], "val")

            # Retrieve
            val = dht.get(b"key")
            self.assertEqual(val, "val")


if __name__ == "__main__":
    unittest.main()
