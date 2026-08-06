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
from unittest import mock

from warm_logic.kernel.mesh.dht import (
    Contact,
    DHTProtocol,
    KBucket,
    RoutingTable,
    SovereignDHT,
)


class TestDHTFinalSaturation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.node_id = b"\x00" * 32
        self.dht = SovereignDHT(
            self.node_id, "127.0.0.1", 4000, public_key=b"PK".ljust(32, b"\x00")
        )
        self.transport = mock.MagicMock()
        self.dht.transport = self.transport
        self.proto = DHTProtocol(self.dht)
        self.proto.transport = self.transport

    def test_contact_edge(self):
        """Line 47, 66-68"""
        c1 = Contact(b"\x01" * 32, "1.1.1.1", 80)
        self.assertFalse(c1 == "not a contact")

        kb = KBucket(0, 2**256)
        kb.update(c1)
        kb.update(c1)
        self.assertEqual(len(kb.get_contacts()), 1)

    async def test_routing_table_revocation(self):
        """Lines 106-112, 117-120, 123"""
        with mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            rt = RoutingTable(self.node_id)
            pk = b"p".ljust(32, b"\x00")
            v_id = hashlib.sha3_256(pk).digest()
            c1 = Contact(v_id, "1.1.1.1", 80, public_key=pk, silicon_id="SID")

            await rt.update(c1)
            self.assertEqual(len(rt.get_all_contacts()), 1)

            rt.revoke_node(v_id)
            self.assertIn(v_id, rt.revoked_nodes)
            self.assertEqual(len(rt.get_all_contacts()), 0)

            self.assertFalse(rt._verify_binding(c1))

            # Line 123
            c_fail = Contact(b"id", "trigger_binding_fail", 80)
            self.assertFalse(rt._verify_binding(c_fail))

    async def test_verify_binding_edge(self):
        """Lines 133-136, 142-146"""
        rt = RoutingTable(self.node_id)
        c_bad_id = Contact(
            b"\xff" * 32,
            "1.1.1.1",
            80,
            public_key=b"p".ljust(32, b"\x00"),
            silicon_id="SID",
        )
        self.assertFalse(rt._verify_binding(c_bad_id))

        pk = b"p".ljust(32, b"\x00")
        v_id = hashlib.sha3_256(pk).digest()
        c_no_sid = Contact(v_id, "1.1.1.1", 80, public_key=pk, silicon_id=None)
        self.assertFalse(rt._verify_binding(c_no_sid))

    async def test_update_eviction(self):
        """Lines 208-225, 211, 194"""
        with (
            mock.patch("warm_logic.kernel.mesh.dht.K_PARAM", 1),
            mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False),
        ):
            rt = RoutingTable(self.node_id)
            p1 = b"z".ljust(32, b"\x00")
            id1 = hashlib.sha3_256(p1).digest()
            c1 = Contact(id1, "1.1.1.1", 80, public_key=p1, silicon_id="SID")

            p2 = b"zz".ljust(32, b"\x00")
            id2 = hashlib.sha3_256(p2).digest()
            c2 = Contact(id2, "2.2.2.2", 80, public_key=p2, silicon_id="SID")

            await rt.update(c1)
            mock_dht = mock.AsyncMock()
            mock_dht.ping.return_value = True
            await rt.update(c2, dht=mock_dht)
            bucket = rt.buckets[1]
            self.assertEqual(bucket.contacts[0], c1)

            # Line 211
            rt._evict_in_progress = True
            await rt.update(c1, dht=mock_dht)

            # Line 194: target_bucket_idx == -1
            with mock.patch.object(rt, "buckets", []):
                await rt.update(c1)

            mock_dht.ping.return_value = False
            bucket.contacts = [c1]
            rt._evict_in_progress = False
            await rt.update(c2, dht=mock_dht)
            self.assertEqual(bucket.contacts[0], c2)

    def test_find_neighbors_rust_success(self):
        """Line 237"""
        rt = RoutingTable(self.node_id)
        rt._use_rust = True
        rt._rust_table = mock.MagicMock()
        target = b"\xff" * 32
        rt._rust_table.find_closest.return_value = [(target, "1.1.1.1", 80)]
        res = rt.find_neighbors(target)
        self.assertEqual(res[0].node_id, target)

    def test_find_neighbors_galaxy(self):
        """Line 276"""
        rt = RoutingTable(self.node_id)
        rt.owner = mock.MagicMock()
        rt.owner.galaxy = mock.MagicMock()
        rt.owner.galaxy.get_topology_score.return_value = 0.5
        c1 = Contact(b"\x01" * 32, "1.1.1.1", 80)
        rt.buckets[0].update(c1)
        res = rt.find_neighbors(b"\x00" * 32)
        self.assertEqual(len(res), 1)

    def test_get_all_contacts_rust(self):
        """Lines 284-308"""
        rt = RoutingTable(self.node_id)
        rt._use_rust = True
        rt._rust_table = mock.MagicMock()
        target = b"\xff" * 32
        rt._rust_table.find_closest.return_value = [(target, "1.1.1.1", 80)]
        c1 = Contact(b"\x01" * 32, "2.2.2.2", 80)
        rt.buckets[0].update(c1)
        all_c = rt.get_all_contacts()
        self.assertEqual(len(all_c), 2)

        rt._rust_table.find_closest.side_effect = Exception("Fail")
        all_c = rt.get_all_contacts()
        self.assertEqual(len(all_c), 1)

    def test_dht_init_fallbacks(self):
        """Lines 340-341, 348-349"""
        with mock.patch.dict(
            "sys.modules",
            {
                "warm_logic.kernel.security.silicon": None,
                "warm_logic.kernel.mesh.capabilities": None,
            },
        ):
            dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
            self.assertEqual(dht.silicon_id, "VIRTUAL_REALITY")
            self.assertEqual(dht.capabilities, {})

    async def test_dht_start_no_nat(self):
        """Lines 388-389"""
        dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
        with mock.patch("warm_logic.kernel.mesh.dht.create_transport") as mock_ct:
            mock_ct.return_value.start_server = mock.AsyncMock()
            await dht.start(enable_nat_discovery=False)
            self.assertEqual(dht.public_address, "1.1.1.1")

    async def test_dht_stop_edge(self):
        """Lines 417-428"""
        dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
        dht.storage = mock.MagicMock()
        dht.storage.close.side_effect = Exception("Close fail")
        dht.transport = mock.MagicMock()
        dht.transport.close.side_effect = Exception("Transport fail")
        await dht.stop()

    async def test_bootstrap_edge(self):
        """Lines 436-449, 452-453"""
        dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
        await dht.bootstrap(seeds=None)

        with (
            mock.patch("os.path.exists", return_value=True),
            mock.patch(
                "builtins.open",
                mock.mock_open(
                    read_data='{"trust_anchors": [{"address": "1.2.3.4", "port": 80}]}'
                ),
            ),
            mock.patch.object(dht, "send"),
        ):
            await dht.bootstrap()

        with (
            mock.patch("os.path.exists", return_value=True),
            mock.patch("builtins.open", side_effect=Exception("parse error")),
        ):
            await dht.bootstrap()

    async def test_iterative_find_node_edge(self):
        """Lines 477, 484, 500-509, 522"""
        dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
        res = await dht.iterative_find_node(b"\xff" * 32)
        self.assertEqual(res, [])

        # Line 484: shortlist exists but asked all
        c1 = Contact(b"\x01" * 32, "1.1.1.1", 80)
        with mock.patch.object(dht.routing, "find_neighbors", side_effect=[[c1], [c1]]):
            await dht.iterative_find_node(b"\x01" * 32)

        pk = b"p".ljust(32, b"\x00")
        v_id = hashlib.sha3_256(pk).digest()
        c1 = Contact(v_id, "1.1.1.1", 80, public_key=pk, silicon_id="SID")
        await dht.routing.update(c1)

        pk2 = b"p2".ljust(32, b"\x00")
        v_id2 = hashlib.sha3_256(pk2).digest()
        response = {
            "type": "NODES",
            "nodes": [{"id": v_id2.hex(), "addr": "2.2.2.2", "port": 80}],
        }
        with (
            mock.patch.object(dht.routing, "_verify_binding", return_value=True),
            mock.patch.object(dht, "rpc_call", return_value=response),
        ):
            res = await dht.iterative_find_node(v_id2)
            self.assertEqual(len(res), 2)

        response_bad = {"type": "NODES", "nodes": [{"id": "not_hex"}]}
        with mock.patch.object(dht, "rpc_call", return_value=response_bad):
            await dht.iterative_find_node(v_id2)

    def test_store_put(self):
        dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
        dht.storage = mock.MagicMock()
        dht.store(b"key", "val")
        dht.storage.put.assert_called()

    def test_broadcast(self):
        dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
        pk = b"p".ljust(32, b"\x00")
        v_id = hashlib.sha3_256(pk).digest()
        c1 = Contact(v_id, "1.1.1.1", 80, public_key=pk, silicon_id="SID")
        dht.routing.buckets[0].update(c1)
        with mock.patch.object(dht, "send") as mock_send:
            dht.broadcast(b"data")
            dht.broadcast_policy_event("inv_1", "active")
        with mock.patch.object(dht, "send", side_effect=Exception("fail")):
            dht.broadcast(b"data")

    def test_broadcast_network_fail(self):
        dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
        with mock.patch.object(dht, "send", side_effect=Exception("fail")):
            dht.broadcast_network(b"msg")

    async def test_ping_full(self):
        dht = SovereignDHT(self.node_id, "1.1.1.1", 80)
        c1 = Contact(b"\x01" * 32, "1.1.1.1", 80)
        dht.galaxy = mock.MagicMock()
        with mock.patch.object(dht, "rpc_call", return_value={"type": "PONG"}):
            self.assertTrue(await dht.ping(c1))
        with mock.patch.object(dht, "rpc_call", side_effect=asyncio.TimeoutError()):
            self.assertFalse(await dht.ping(c1))
        with mock.patch.object(dht, "rpc_call", side_effect=Exception("error")):
            self.assertFalse(await dht.ping(c1))

    async def test_protocol_handlers(self):
        self.dht.routing.update = mock.AsyncMock()
        req_id = "req_1"
        self.dht._requests[req_id] = asyncio.Future()
        msg = {"type": "NODES", "sender_id": self.node_id.hex(), "msg_id": req_id}
        self.proto.datagram_received(json.dumps(msg).encode(), ("1.1.1.1", 80))
        await asyncio.sleep(0.01)
        self.assertTrue(self.dht._requests[req_id].done())

        handlers = [
            "PING",
            "FIND_NODE",
            "MANIFEST_ANNOUNCE",
            "MERKLE_ROOT_REQUEST",
            "SUBTREE_HASHES_REQUEST",
            "SUBTREE_RECORDS_REQUEST",
            "STORE_VALUE",
            "MUTATION_PROPOSAL",
            "MUTATION_VOTE",
            "POLICY_UPDATE",
            "REVOKE_NODE",
            "ZANZIBAR_TUPLE",
        ]
        for mtype in handlers:
            msg = {"type": mtype, "sender_id": self.node_id.hex()}
            if mtype == "FIND_NODE":
                msg["target_id"] = self.node_id.hex()
            if mtype == "STORE_VALUE":
                msg.update(
                    {"key": "k", "value": "v", "zk_proof": "zk", "commitment": "c"}
                )
            if mtype == "REVOKE_NODE":
                msg["revoke_id"] = self.node_id.hex()
            if mtype == "ZANZIBAR_TUPLE":
                msg.update(
                    {
                        "namespace": "n",
                        "object_id": "o",
                        "relation": "r",
                        "subject_namespace": "sn",
                        "subject_id": "si",
                    }
                )
            self.proto.datagram_received(json.dumps(msg).encode(), ("1.1.1.1", 80))
            await asyncio.sleep(0.01)

    def test_handle_manifest_announce_edge(self):
        self.proto.handle_manifest_announce(
            {"type": "MANIFEST_ANNOUNCE", "sender_id": ""}, ("1.1.1.1", 80)
        )
        self.dht.gossip_agent = mock.MagicMock()
        msg = {"type": "MANIFEST_ANNOUNCE", "sender_id": "01", "manifest_hash": "hash"}
        self.proto.handle_manifest_announce(msg, ("1.1.1.1", 80))
        del self.dht.gossip_agent.on_receive_manifest
        self.dht.gossip_agent.receive_manifest = mock.MagicMock()
        self.proto.handle_manifest_announce(msg, ("1.1.1.1", 80))

    def test_entropy_handlers(self):
        self.dht.anti_entropy_agent = mock.MagicMock()
        self.dht.anti_entropy_agent.rebuild_merkle.return_value = "root"
        self.dht.anti_entropy_agent._merkle.get_subtree_hashes.return_value = ["h1"]
        self.dht.anti_entropy_agent._get_local_state.return_value = {"k": "v"}
        self.proto.handle_merkle_root_request({}, ("1.1.1.1", 80))
        self.proto.handle_subtree_hashes_request({}, ("1.1.1.1", 80))
        self.proto.handle_subtree_records_request({}, ("1.1.1.1", 80))

    def test_handle_store_value_acl_zk(self):
        self.dht.storage = mock.MagicMock(spec=dict)
        self.dht.storage.__setitem__.side_effect = Exception("fail")
        msg = {
            "key": "k",
            "value": "v",
            "zk_proof": "zk",
            "commitment": "c",
            "sender_id": "01",
        }

        # Line 906-917: ACL check error
        with mock.patch(
            "warm_logic.kernel.mesh.dht.check_permission",
            side_effect=Exception("acl fail"),
        ):
            self.proto.handle_store_value_request(msg, ("1.1.1.1", 80))

        # Line 925-926: ZK verify exception
        with (
            mock.patch(
                "warm_logic.kernel.mesh.dht.check_permission", return_value=True
            ),
            mock.patch(
                "warm_logic_rs.RustZKProofGenerator", side_effect=Exception("zk fail")
            ),
        ):
            self.proto.handle_store_value_request(msg, ("1.1.1.1", 80))

        # Normal flow with storage exception
        with (
            mock.patch(
                "warm_logic.kernel.mesh.dht.check_permission", return_value=True
            ),
            mock.patch("warm_logic_rs.RustZKProofGenerator") as mock_zk,
        ):
            mock_zk.return_value.verify_state_proof.return_value = True
            self.proto.handle_store_value_request(msg, ("1.1.1.1", 80))

    def test_mutation_handlers(self):
        self.dht.fleet_manager = mock.MagicMock()
        self.proto.handle_mutation_proposal({}, ("1.1.1.1", 80))
        self.proto.handle_mutation_vote({}, ("1.1.1.1", 80))

    def test_patch_revoke_handlers(self):
        self.proto.handle_patch_request({"target_hash": "h"}, ("1.1.1.1", 80))
        self.proto.handle_patch_request({}, ("1.1.1.1", 80))
        with mock.patch.object(self.dht.routing, "revoke_node") as mock_revoke:
            self.proto.handle_revoke_node(
                {"revoke_id": self.node_id.hex()}, ("1.1.1.1", 80)
            )

    def test_zanzibar_handler(self):
        msg = {
            "namespace": "n",
            "object_id": "o",
            "relation": "r",
            "subject_namespace": "sn",
            "subject_id": "si",
        }
        with mock.patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple"
        ) as mock_write:
            self.proto.handle_zanzibar_tuple(msg, ("1.1.1.1", 80))
        with mock.patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple",
            side_effect=Exception("fail"),
        ):
            self.proto.handle_zanzibar_tuple(msg, ("1.1.1.1", 80))

    async def test_surgical_precision(self):
        """Lines 674, 812, 955, 958, 977"""
        _ = self.dht.server
        self.dht.service_registry = mock.MagicMock()
        for mtype in [
            "SERVICE_REGISTRATION_PROPOSAL",
            "SERVICE_REGISTRATION_VOTE",
            "INSIGHT_ANNOUNCE",
            "POLICY_UPDATE",
        ]:
            msg = {"type": mtype, "sender_id": self.node_id.hex()}
            self.proto.datagram_received(json.dumps(msg).encode(), ("1.1.1.1", 80))
            await asyncio.sleep(0.01)
        self.proto.handle_find_node({"type": "FIND_NODE"}, ("1.1.1.1", 80))
        self.proto.handle_revoke_node({"type": "REVOKE_NODE"}, ("1.1.1.1", 80))

        # Line 674: Trigger RPC exception to hit finally
        with mock.patch.object(self.dht, "send", side_effect=Exception("RPC Fail")):
            try:
                await self.dht.rpc_call(Contact(b"id", "1.1.1.1", 80), {})
            except Exception:
                pass  # Expected: RPC failure triggers finally block


if __name__ == "__main__":
    unittest.main()
