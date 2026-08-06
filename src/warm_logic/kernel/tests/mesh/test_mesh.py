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
import asyncio
import unittest
from unittest import mock
from unittest.mock import patch

from warm_logic.kernel.mesh.dht import (
    Contact,
    DHTProtocol,
    KBucket,
    RoutingTable,
    SovereignDHT,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


@mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False)
class TestMesh(WarmLogicTestCase):
    def setUp(self):
        self.node_id = b"\x01" * 32
        self.local_id = Contact(b"\x00" * 20, "127.0.0.1", 8000)
        self.dht = SovereignDHT(self.node_id, "127.0.0.1", 8001)

    def tearDown(self):
        self.dht = None

    def test_kbucket_overflow(self):
        # Line 50: Bucket overflow
        bucket = KBucket(0, 100)
        from warm_logic.kernel.mesh.dht import K_PARAM

        for i in range(K_PARAM):
            c = Contact(i.to_bytes(32, "big"), "127.0.0.1", 9000 + i)
            bucket.update(c)

        # Overflow
        overflow_c = Contact(b"\xff" * 32, "127.0.0.1", 9999)
        res = bucket.update(overflow_c)
        self.assertFalse(res)

    async def test_routing_table_split_recursive(self):
        # This test relies on internal Python implementation (buckets).
        # Skip if running in Rust/Metal mode where buckets don't exist.
        if self.dht.routing._use_rust:
            return

        # Line 83: Recursive split
        rt = self.dht.routing
        # Ensure we are in pure python mode for this test logic to make sense
        if hasattr(rt, "buckets") and not rt.buckets:
            rt.buckets = [KBucket(0, 2**256)]
        # Line 123: split_bucket(i)
        # rt = RoutingTable(self.node_id) # This line is commented out as it's replaced by `rt = self.dht.routing`
        rt._use_rust = False
        from warm_logic.kernel.mesh.dht import K_PARAM

        # Add many contacts close to self to force splitting
        for i in range(K_PARAM + 5):
            # node_id must pass _verify_binding
            import hashlib

            pk = i.to_bytes(32, "big")
            node_id = hashlib.sha256(pk).digest()
            c = Contact(node_id, "127.0.0.1", 10000 + i, public_key=pk)
            await rt.update(c)
        self.assertTrue(len(rt.buckets) > 1)

    def test_routing_table_binding_fail(self):
        # Line 71, 74: binding fails
        rt = RoutingTable(self.node_id)
        c_fail = Contact(b"id", "trigger_binding_fail", 8080)
        self.assertFalse(rt._verify_binding(c_fail))

        c_no_pk = Contact(b"id", "127.0.0.1", 8080, public_key=None)
        self.assertFalse(rt._verify_binding(c_no_pk))

    def test_protocol_error_handling(self):
        # Line 234: datagram_received exception
        proto = DHTProtocol(self.dht)
        # Invalid JSON
        with self.assertLogs("SovereignMesh", level="ERROR") as cm:
            proto.datagram_received(b"not json", ("127.0.0.1", 9999))
            self.assertTrue(
                any("Error handling DHT message" in line for line in cm.output)
            )

    def test_dht_protocol_messages(self):
        """Cover valid PING and FIND_NODE handling"""
        proto = DHTProtocol(self.dht)
        import json

        # 1. PING
        ping_msg = json.dumps(
            {
                "type": "PING",
                "sender_id": self.node_id.hex(),
                "sender_pk": self.node_id.hex(),  # mock pk
            }
        ).encode()

        # We invoke datagram_received. It should update routing and handle ping.
        # We can mock routing.update or just let it run (it validates binding)
        # Mock _verify_binding to be true
        with patch.object(self.dht.routing, "_verify_binding", return_value=True):
            proto.datagram_received(ping_msg, ("127.0.0.1", 9999))
            # Coverage will hit handle_ping -> response

        # 2. FIND_NODE
        fn_msg = json.dumps(
            {
                "type": "FIND_NODE",
                "sender_id": self.node_id.hex(),
                "target_id": self.node_id.hex(),
            }
        ).encode()

        with patch.object(self.dht.routing, "_verify_binding", return_value=True):
            # Mock routing.find_neighbors
            with patch.object(self.dht.routing, "find_neighbors", return_value=[]):
                proto.datagram_received(fn_msg, ("127.0.0.1", 9999))
                # Coverage hit handle_find_node

    def test_iterative_find_node_empty(self):
        # Line 181: if not shortlist
        with patch.object(self.dht.routing, "find_neighbors", return_value=[]):
            res = asyncio.run(self.dht.iterative_find_node(b"target"))
            self.assertEqual(res, [])

    def test_iterative_find_node_success(self):
        """Cover iterative lookup loop (lines 184+)"""
        # Mock routing response to simulation peer discovery
        c = Contact(b"\x02" * 32, "127.0.0.1", 9000)
        # We Mock find_neighbors to return a contact so the loop logic runs
        with patch.object(self.dht.routing, "find_neighbors", return_value=[c]):
            res = asyncio.run(self.dht.iterative_find_node(b"target"))
            # It should run loop and return
            self.assertIsNotNone(res)

    def test_bootstrap_simulation(self):
        # Covering bootstrap method
        asyncio.run(self.dht.bootstrap([("127.0.0.1", 8000)]))


if __name__ == "__main__":
    unittest.main()
