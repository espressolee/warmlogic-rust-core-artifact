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
import hashlib
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark tests to run in same xdist group to avoid rust_loader patch conflicts
pytestmark = pytest.mark.xdist_group("legacy_recovery")

from warm_logic.kernel.economy.ledger import ReplicatedLedger
from warm_logic.kernel.mesh.dht import (
    K_PARAM,
    Contact,
    DHTProtocol,
    RoutingTable,
    SovereignDHT,
)
from warm_logic.kernel.sys.persistence import SovereignStore


# Helper to generate ID
def gen_id(byte_byte=b"\x00"):
    return byte_byte * 32


def gen_contact(i):
    b = bytes([i]) + b"\x00" * 31
    # For valid binding, we need pk such that sha256(pk) == id
    # Mock hashlib.sha256 to return id for our "pk"
    return Contact(b, "127.0.0.1", 8000 + i, public_key=b"pk")


class TestLegacyRecovery(unittest.TestCase):
    # --- DHT Recovery ---
    def test_dht_python_routing(self):
        # Force Python Mode
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            my_id = gen_id(b"\xff")
            rt = RoutingTable(my_id)

            # 1. Verify Binding (Python)
            # Valid - Uses SHA3-256, not SHA-256
            # Also requires silicon_id
            c_valid = Contact(
                hashlib.sha3_256(b"pk").digest(),
                "addr",
                1,
                public_key=b"pk",
                silicon_id=b"silicon_test",
            )
            self.assertTrue(rt._verify_binding(c_valid))

            # Invalid (No PK)
            c_no_pk = Contact(b"id", "addr", 1, None)
            self.assertFalse(rt._verify_binding(c_no_pk))

            # Invalid (Mismatch)
            c_bad = Contact(b"\x00" * 32, "addr", 1, public_key=b"pk")
            self.assertFalse(rt._verify_binding(c_bad))

            # Trigger Fail
            c_trig = Contact(b"id", "trigger_binding_fail", 1)
            self.assertFalse(rt._verify_binding(c_trig))

            # 2. Update & Bucket Split
            # We need to fill a bucket. K_PARAM=20.
            # We mock _verify_binding to True for simplicity in bulk

            async def run_updates():
                with patch.object(rt, "_verify_binding", return_value=True):
                    # Update Self (Ignored)
                    await rt.update(Contact(my_id, "addr", 0))
                    self.assertEqual(len(rt.buckets[0].contacts), 0)

                    # Fill Bucket
                    for i in range(K_PARAM):
                        c = gen_contact(i)
                        await rt.update(c)
                    self.assertEqual(len(rt.buckets[0].contacts), K_PARAM)

                    # Overflow -> Split
                    # To trigger split, new contact must be in range of local_id
                    # and bucket must be full.
                    # Our local_id is FF... (Very high).
                    # Current bucket is 0..2**256.
                    # When we split, we get 0..MID and MID..MAX.
                    # FF... is in upper.
                    # Contacts 0..20 are in lower.

                    # Add a contact close to self (FF..FE)
                    c_near = Contact(
                        b"\xff" * 31 + b"\xfe", "addr", 9000, public_key=b"pk"
                    )
                    await rt.update(c_near)

                    # Should have split
                    self.assertTrue(len(rt.buckets) > 1)

                    # Verify split distribution
                    # Lower bucket should have the 0..20 contacts
                    # Upper bucket should have c_near

            asyncio.run(run_updates())

            # 3. Find Neighbors (Python)
            target = b"\x00" * 32
            neighbors = rt.find_neighbors(target, count=5)
            self.assertEqual(len(neighbors), 5)
            # First should be closest (00...)
            self.assertEqual(neighbors[0].node_id.hex()[:2], "00")

    async def async_test_dht_iterative(self):
        # Force Python Mode
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            dht = SovereignDHT(gen_id(b"\x01"), "localhost", 8000)

            # Mock routing find to simulate network discovery
            # Iteration 1: Returns [Near]
            # Iteration 2: Returns [Nearer]
            # Iteration 3: No change

            c1 = gen_contact(10)
            c2 = gen_contact(20)  # Closer to target? XOR math...

            dht.routing.find_neighbors = MagicMock(
                side_effect=[[c1], [c1, c2], [c1, c2]]
            )

            res = await dht.iterative_find_node(b"\x00" * 32)
            self.assertTrue(len(res) > 0)

            # Bootstrap
            dht.iterative_find_node = AsyncMock()
            await dht.bootstrap([("1.1.1.1", 5000)])
            dht.iterative_find_node.assert_called()

    def test_dht_protocol(self):
        dht = MagicMock()
        dht.node_id = b"\x01" * 32
        # Make routing.update return a coroutine that can be awaited
        dht.routing.update = AsyncMock()
        proto = DHTProtocol(dht)

        addr = ("1.2.3.4", 1234)

        async def run_protocol_tests():
            # 1. PING
            msg = json.dumps(
                {
                    "type": "PING",
                    "sender_id": gen_id(b"\x02").hex(),
                    "sender_pk": gen_id(b"\x02").hex(),  # Fake PK match
                }
            ).encode()
            proto.datagram_received(msg, addr)
            # Give time for create_task to execute
            await asyncio.sleep(0.01)
            dht.routing.update.assert_called()

            # 2. FIND_NODE
            dht.routing.find_neighbors.return_value = [gen_contact(1)]
            msg_fn = json.dumps(
                {
                    "type": "FIND_NODE",
                    "target_id": "00" * 32,
                    "sender_id": gen_id(b"\x03").hex(),
                }
            ).encode()
            proto.datagram_received(msg_fn, addr)
            await asyncio.sleep(0.01)
            dht.routing.find_neighbors.assert_called()

            # 3. Bad JSON
            proto.datagram_received(b"{bad", addr)
            # Should log error but not crash

        asyncio.run(run_protocol_tests())

    def test_dht_async_wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.async_test_dht_iterative())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    # --- Ledger Recovery ---
    def test_ledger_legacy_mining(self):
        store = MagicMock(spec=SovereignStore)
        store.get_balance.return_value = 1000
        store.get_all_balances.return_value = {}

        # Force Legacy (Should Fail in a later revision)
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            # Also patch sys.modules to ensure no rust module found if logic checks imports
            with patch.dict("sys.modules", {"warm_logic_rs": None}):
                # FIX: Re-init ReplicatedLedger
                with self.assertRaises(RuntimeError):
                    ReplicatedLedger(store)
