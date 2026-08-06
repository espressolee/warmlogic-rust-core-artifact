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
import hashlib
from unittest import mock

from warm_logic.kernel.mesh.dht import (
    K_PARAM,
    Contact,
    DHTProtocol,
    KBucket,
    RoutingTable,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


@mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False)
class TestDHTFinalSurgical(WarmLogicTestCase):
    async def test_routing_table_surgical(self):
        rt = RoutingTable(b"\x00" * 32)

        # 1. Self filter (line 106)
        c_self = Contact(
            b"\x00" * 32, "1.1.1.1", 80, public_key=b"k" * 32, silicon_id="SID"
        )
        await rt.update(c_self)  # Should return early (async)

        # 2. Split logic (lines 87-101)
        # We need to fill a bucket that contains the local ID to trigger split_bucket
        # Local ID is 0. Bucket is [0, 2^256-1].
        # _verify_binding requires sha3_256 hash matching, so we mock it
        with mock.patch.object(rt, "_verify_binding", return_value=True):
            for i in range(K_PARAM + 1):
                pk = f"node_pk_{i}".encode()
                rid = hashlib.sha256(pk).digest()
                await rt.update(Contact(rid, "1.1.1.1", i, public_key=pk))
        self.assertGreater(len(rt.buckets), 1)

    async def test_dht_protocol_handlers(self):
        dht = mock.MagicMock()
        dht.node_id = b"\x00" * 32
        proto = DHTProtocol(dht)

        # PING handle (lines 260-263)
        msg_ping = {"type": "PING", "sender_id": ("01" * 32)}
        proto.handle_ping(msg_ping, ("1.1.1.1", 80))

        # FIND_NODE handle (lines 271-282)
        msg_find = {"type": "FIND_NODE", "target_id": ("02" * 32)}
        dht.routing.find_neighbors.return_value = [Contact(b"\x03" * 32, "3.3.3.3", 80)]
        proto.handle_find_node(msg_find, ("1.1.1.1", 80))

    async def test_kbucket_surgical(self):
        kb = KBucket(0, 100)
        # Filling
        for i in range(K_PARAM):
            kb.update(Contact(i.to_bytes(32, "big"), "1.1.1.1", i))

        # Overflow returns False in a later revision
        res = kb.update(Contact(b"\xff" * 32, "1.1.1.1", 99))
        self.assertFalse(res)
