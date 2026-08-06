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
from unittest import mock

from warm_logic.kernel.mesh.dht import (
    Contact,
    DHTProtocol,
    KBucket,
    RoutingTable,
    SovereignDHT,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestDHTCoverage(WarmLogicTestCase):
    def test_contact(self):
        c1 = Contact(b"\x01" * 32, "127.0.0.1", 8000)
        c2 = Contact(b"\x01" * 32, "127.0.0.1", 8000)
        self.assertEqual(c1, c2)

    def test_kbucket(self):
        kb = KBucket(0, 2**256)
        c1 = Contact(b"\x01" * 32, "127.0.0.1", 8000)
        kb.update(c1)
        self.assertEqual(len(kb.get_contacts()), 1)

    async def test_routing_table_python(self):
        with mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            node_id = b"\x00" * 32
            rt = RoutingTable(node_id)
            import hashlib

            pk = b"valid_pub_key".ljust(32, b"\x00")
            # Use sha3_256 to match DHT's binding verification
            valid_id = hashlib.sha3_256(pk).digest()
            c_valid = Contact(valid_id, "1.2.3.4", 80, public_key=pk, silicon_id="SID")
            await rt.update(c_valid)
            neighbors = rt.find_neighbors(valid_id)
            self.assertEqual(neighbors[0], c_valid)

    def test_routing_table_rust_fail_init(self):
        with mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with mock.patch(
                "warm_logic.kernel.rust_loader.load_rust_core"
            ) as mock_load:
                mock_load.return_value.RustRoutingTable.side_effect = Exception(
                    "Init Fail"
                )
                rt = RoutingTable(b"\x00" * 32)
                self.assertFalse(rt._use_rust)

    async def test_routing_table_rust_method_fail(self):
        with mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with mock.patch(
                "warm_logic.kernel.rust_loader.load_rust_core"
            ) as mock_load:
                mock_rt = mock.MagicMock()
                mock_load.return_value.RustRoutingTable.return_value = mock_rt

                rt = RoutingTable(b"\x00" * 32)
                self.assertTrue(rt._use_rust)

                # update fail
                import hashlib

                pk = b"p".ljust(32, b"\x00")
                # Use sha3_256 to match DHT's binding verification
                cid = hashlib.sha3_256(pk).digest()
                mock_rt.update.side_effect = Exception("Update Fail")
                await rt.update(
                    Contact(cid, "1.1.1.1", 80, public_key=pk, silicon_id="SID")
                )

                # If update failed in Rust, it fell back to Python.
                # Since cid != local_id and pk is valid, it should be in Python table.

                # find_closest fail
                mock_rt.find_closest.side_effect = Exception("Find Fail")
                res = rt.find_neighbors(b"\x01" * 32)
                self.assertEqual(
                    len(res), 1
                )  # Should find the one we added to Python fallback

    async def test_routing_table_binding_fail(self):
        rt = RoutingTable(b"\x00" * 32)
        c_fail = Contact(b"\x01" * 32, "trigger_binding_fail", 80)
        await rt.update(c_fail)
        self.assertEqual(len(rt.find_neighbors(b"\x01" * 32)), 0)

    def test_dht_protocol(self):
        dht = mock.MagicMock()
        dht.node_id = b"\x00" * 32
        proto = DHTProtocol(dht)
        msg = f'{{"type": "PING", "sender_id": "{("01" * 32)}", "sender_pk": "{("ff" * 32)}"}}'.encode()
        proto.datagram_received(msg, ("127.0.0.1", 8000))

    async def test_sovereign_dht_basic(self):
        node_id = b"\x00" * 32
        dht = SovereignDHT(node_id, "127.0.0.1", 4000)
        with mock.patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = mock.AsyncMock(
                return_value=(mock.MagicMock(), None)
            )
            await dht.start()
        dht.store(b"k", "v")
        self.assertEqual(dht.get(b"k"), "v")
        dht.send(Contact(b"\x01", "1.1.1.1", 80), b"m")

    async def test_iterative_find_node(self):
        dht = SovereignDHT(b"\x00" * 32, "127.0.0.1", 4000)
        import hashlib

        pk = b"p".ljust(32, b"\x00")
        # Use sha3_256 to match DHT's binding verification
        cid = hashlib.sha3_256(pk).digest()
        c1 = Contact(cid, "1.1.1.1", 80, public_key=pk, silicon_id="SID")
        await dht.routing.update(c1)
        res = await dht.iterative_find_node(cid)
        self.assertIn(c1, res)

    async def test_bootstrap(self):
        dht = SovereignDHT(b"\x00" * 32, "127.0.0.1", 4000)
        with mock.patch.object(dht, "iterative_find_node") as mock_find:
            await dht.bootstrap([("seed", 80)])
            mock_find.assert_called()

    def test_sync_find_node(self):
        dht = SovereignDHT(b"\x00" * 32, "127.0.0.1", 4000)
        dht.find_node(b"\x01" * 32)
