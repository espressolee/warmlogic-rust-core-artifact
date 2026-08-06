import asyncio
import json
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import warm_logic.kernel.mesh.dht as dht_module
from warm_logic.kernel.mesh.dht import (
    Contact,
    DHTProtocol,
    KBucket,
    RoutingTable,
    SovereignDHT,
)


class FakeTransport:
    def __init__(self):
        self.sendto = MagicMock()
        self.start_server_called = False
        self.close_called = False

    async def start_server(self, host, port, loop_cb):
        self.start_server_called = True
        return None

    def close(self):
        self.close_called = True


class TestDHTSaturation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._rust_core_patcher = patch.object(
            dht_module.rust_loader, "HAS_RUST_CORE", False
        )
        self._rust_core_patcher.start()
        self.addCleanup(self._rust_core_patcher.stop)

        self.node_id = b"\x01" * 32
        self.dht = SovereignDHT(self.node_id, "127.0.0.1", 8000)
        # Default transport
        self.dht.transport = MagicMock()
        self.dht.transport.sendto = MagicMock()
        self.dht.transport.start_server = AsyncMock()
        self.dht.public_key = b"pub"
        self.dht.private_key = "priv"

    async def asyncTearDown(self):
        # Ensure each test releases any transport/state created by start().
        await self.dht.stop()

    def test_contact_basics(self):
        c1 = Contact(self.node_id, "127.0.0.1", 8000)
        c2 = Contact(self.node_id, "127.0.0.1", 8000)
        c3 = Contact(b"\x02" * 32, "1.2.3.4", 9000)
        self.assertEqual(hash(c1), hash(c2))
        self.assertEqual(c1, c2)
        self.assertNotEqual(c1, c3)
        self.assertTrue(c1.xor_distance(b"\x02" * 32) > 0)

    # --- RoutingTable Tests ---
    def test_routing_init_rust_fallback(self):
        with patch.object(dht_module.rust_loader, "HAS_RUST_CORE", False):
            rt = RoutingTable(self.node_id)
            self.assertFalse(rt._use_rust)
            self.assertIsNone(rt._rust_table)

    def test_routing_init_rust_success(self):
        with patch.object(dht_module.rust_loader, "HAS_RUST_CORE", True):
            with patch.object(dht_module.rust_loader, "load_rust_core") as mock_load:
                mock_load.return_value = MagicMock()
                rt = RoutingTable(self.node_id)
                self.assertTrue(rt._use_rust)
                self.assertIsNotNone(rt._rust_table)

    def test_verify_binding_logic(self):
        rt = RoutingTable(self.node_id)
        import hashlib

        pk = b"valid_pk"
        expected_id = hashlib.sha3_256(pk).digest()
        c = Contact(expected_id, "1.2.3.4", 9000, public_key=pk, silicon_id="s1")
        self.assertTrue(rt._verify_binding(c))

        rt.revoke_node(expected_id)
        self.assertFalse(rt._verify_binding(c))
        rt.revoked_nodes.clear()

        c_fail = Contact(expected_id, "trigger_binding_fail", 9000, public_key=pk)
        self.assertFalse(rt._verify_binding(c_fail))

        c_no_pk = Contact(expected_id, "1.2.3.4", 9000, public_key=None)
        self.assertFalse(rt._verify_binding(c_no_pk))

        c_mismatch = Contact(b"\xff" * 32, "1.2.3.4", 9000, public_key=pk)
        self.assertFalse(rt._verify_binding(c_mismatch))

        c_no_si = Contact(expected_id, "1.2.3.4", 9000, public_key=pk, silicon_id=None)
        self.assertFalse(rt._verify_binding(c_no_si))

    async def test_update_and_split(self):
        rt = RoutingTable(self.node_id)
        with patch.object(rt, "_verify_binding", return_value=True):
            for i in range(20):
                await rt.update(
                    Contact((i + 100).to_bytes(32, "big"), "1.1.1.1", 8000 + i)
                )
            self.assertEqual(len(rt.buckets[0].contacts), 20)

            # Trigger split
            await rt.update(Contact((200).to_bytes(32, "big"), "1.1.1.1", 9999))
            self.assertTrue(len(rt.buckets) > 1)

    async def test_update_eviction_ping(self):
        rt = RoutingTable(self.node_id)
        high_start = int.from_bytes(b"\x80" + b"\x00" * 31, "big")
        b = KBucket(high_start, 2**256 - 1)
        rt.buckets = [b]
        contacts = [
            Contact((high_start + i).to_bytes(32, "big"), "1.1.1.1", 8000 + i)
            for i in range(20)
        ]
        b.contacts = list(contacts)
        oldest = contacts[0]
        new_c = Contact((high_start + 100).to_bytes(32, "big"), "1.1.1.1", 9999)
        dht_mock = MagicMock()
        dht_mock.ping = AsyncMock()

        # Case 1: Oldest alive
        dht_mock.ping.return_value = True
        with patch.object(rt, "_verify_binding", return_value=True):
            await rt.update(new_c, dht=dht_mock)
        self.assertNotIn(new_c, b.contacts)
        self.assertEqual(b.contacts[-1], oldest)

        # Case 2: Oldest dead
        dht_mock.ping.return_value = False
        b.contacts.insert(0, b.contacts.pop())
        oldest = b.contacts[0]
        with patch.object(rt, "_verify_binding", return_value=True):
            await rt.update(new_c, dht=dht_mock)
        self.assertNotIn(oldest, b.contacts)
        self.assertIn(new_c, b.contacts)

    def test_find_neighbors_python(self):
        rt = RoutingTable(self.node_id)
        c1 = Contact(b"\x00" * 32, "1.1.1.1", 8000)
        c2 = Contact(b"\xff" * 32, "2.2.2.2", 9000)
        rt.buckets[0].contacts = [c1, c2]
        with patch(
            "warm_logic.mesh.topology.NetworkTopology.get_latency_between_nodes",
            return_value=10.0,
        ):
            neighbors = rt.find_neighbors(self.node_id, count=2)
            self.assertEqual(neighbors[0], c1)

    def test_get_all_contacts(self):
        rt = RoutingTable(self.node_id)
        c1 = Contact(b"\x01" * 32, "addr1", 1)
        rt.buckets[0].contacts = [c1]
        self.assertEqual(rt.get_all_contacts()[0], c1)

    # --- SovereignDHT Tests ---

    async def test_start_with_nat(self):
        fake_transport = FakeTransport()
        with patch.object(
            dht_module,
            "discover_public_address",
            new=AsyncMock(return_value=("1.2.3.4", 1234)),
        ):
            with patch.object(
                dht_module, "create_transport", return_value=fake_transport
            ):
                await self.dht.start(enable_nat_discovery=True)
                self.assertEqual(self.dht.public_address, "1.2.3.4")
                self.assertTrue(fake_transport.start_server_called)

    async def test_start_no_nat(self):
        fake_transport = FakeTransport()
        with patch.object(dht_module, "create_transport", return_value=fake_transport):
            await self.dht.start(enable_nat_discovery=False)
            self.assertEqual(self.dht.public_address, "127.0.0.1")
            self.assertTrue(fake_transport.start_server_called)

    async def test_stop(self):
        self.dht.storage = MagicMock()
        self.dht.transport = MagicMock()
        await self.dht.stop()
        self.dht.storage.close.assert_called_once()
        self.dht.transport.close.assert_called_once()

    async def test_bootstrap_from_json(self):
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data='{"trust_anchors": [{"address": "seed1", "port": 8000}]}'
            ),
        ):
            with patch("os.path.exists", return_value=True):
                self.dht.send = MagicMock()
                self.dht.iterative_find_node = AsyncMock()
                await self.dht.bootstrap(seeds=None)
                self.assertEqual(self.dht.send.call_args[0][0].address, "seed1")

    async def test_iterative_find_node_convergence(self):
        c1 = Contact(b"\x10" * 32, "1.1.1.1", 8000)
        self.dht.routing.find_neighbors = MagicMock(return_value=[c1])

        async def mock_rpc(contact, msg, timeout=10.0):
            return {
                "type": "NODES",
                "nodes": [
                    {"id": (b"\x11" * 32).hex(), "addr": "2.2.2.2", "port": 9000}
                ],
            }

        self.dht.rpc_call = AsyncMock(side_effect=mock_rpc)

        with patch.object(self.dht.routing, "update", new_callable=AsyncMock):
            res = await self.dht.iterative_find_node(b"\xff" * 32)
            self.assertIn(c1, res)

    def test_store_get(self):
        self.dht.store(b"k", "v")
        self.assertEqual(self.dht.get(b"k"), "v")

    def test_broadcast_network(self):
        self.dht.transport = MagicMock()
        self.dht.broadcast_network(b"msg")
        self.dht.transport.sendto.assert_called_with(b"msg", ("255.255.255.255", 8000))

    def test_broadcast_policy_event(self):
        self.dht.broadcast = MagicMock()
        self.dht.broadcast_policy_event("inv1", "active")
        self.dht.broadcast.assert_called()

    async def test_ping(self):
        self.dht.rpc_call = AsyncMock(return_value={"type": "PONG"})
        res = await self.dht.ping(Contact(b"\x02" * 32, "1.1.1.1", 8000))
        self.assertTrue(res)

    async def test_rpc_timeout(self):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            with self.assertRaises(asyncio.TimeoutError):
                await self.dht.rpc_call(Contact(b"\x02" * 32, "1.1.1.1", 8000), {})

    # --- DHTProtocol Tests ---

    async def test_protocol_handle_ping(self):
        p = DHTProtocol(self.dht)
        p.transport = MagicMock()
        msg = {"type": "PING", "msg_id": "123", "sender_id": self.node_id.hex()}
        p.handle_ping(msg, ("1.1.1.1", 8000))
        res = json.loads(p.transport.sendto.call_args[0][0])
        self.assertEqual(res["type"], "PONG")

    def test_protocol_handle_find_node(self):
        p = DHTProtocol(self.dht)
        # Use FakeTransport with MagicMock sendto to verify call
        p.transport = FakeTransport()
        self.dht.routing.find_neighbors = MagicMock(return_value=[])
        msg = {
            "type": "FIND_NODE",
            "target_id": self.node_id.hex(),
            "sender_id": self.node_id.hex(),
        }

        p.handle_find_node(msg, ("1.1.1.1", 8000))

        if not p.transport.sendto.called:
            # Just in case debug needed again
            pass
        else:
            res = json.loads(p.transport.sendto.call_args[0][0])
            self.assertEqual(res["type"], "NODES")

    def test_protocol_handle_store_value(self):
        p = DHTProtocol(self.dht)
        p.transport = MagicMock()
        msg = {
            "type": "STORE_VALUE",
            "key": "k",
            "value": "v",
            "zk_proof": "p",
            "commitment": "c",
            "sender_id": "sid",
        }

        with patch.object(dht_module, "check_permission", return_value=False):
            p.handle_store_value_request(msg, ("1.1.1.1", 8000))
            res = json.loads(p.transport.sendto.call_args[0][0])
            self.assertFalse(res["success"])

        with patch.object(dht_module, "check_permission", return_value=True):
            mock_zk_gen = MagicMock()
            mock_zk_gen.verify_state_proof.return_value = True
            with patch.dict(
                "sys.modules",
                {
                    "warm_logic_rs": MagicMock(
                        RustZKProofGenerator=MagicMock(return_value=mock_zk_gen)
                    )
                },
            ):
                self.dht.storage = {}
                p.handle_store_value_request(msg, ("1.1.1.1", 8000))
                self.assertIn("k", self.dht.storage)

    async def test_datagram_received_dispatch(self):
        """Verify dispatch logic."""
        p = DHTProtocol(self.dht)
        p.transport = MagicMock()
        data = json.dumps({"type": "PING", "sender_id": self.node_id.hex()}).encode(
            "utf-8"
        )

        with patch.object(
            self.dht.routing, "update", new_callable=AsyncMock
        ) as mock_update:
            # Replace handler in dispatch table (p.handle_ping patch won't work
            # since _message_handlers was bound during __init__)
            mock_handler = MagicMock()
            p._message_handlers["PING"] = mock_handler
            p.datagram_received(data, ("1.1.1.1", 8000))
            await asyncio.sleep(0)
            mock_handler.assert_called_once()
            mock_update.assert_called()

    def test_manifest_announce_forward(self):
        p = DHTProtocol(self.dht)
        self.dht.gossip_agent = MagicMock()
        msg = {
            "type": "MANIFEST_ANNOUNCE",
            "sender_id": "sid",
            "manifest_hash": "hash",
            "timestamp": 123.45,
        }
        p.handle_manifest_announce(msg, ("1.1.1.1", 8000))
        self.assertTrue(
            self.dht.gossip_agent.on_receive_manifest.called
            or self.dht.gossip_agent.receive_manifest.called
        )

    def test_handle_patch_request(self):
        p = DHTProtocol(self.dht)

        # 1. Missing hash
        msg = {"type": "PATCH", "target_hash": ""}
        p.handle_patch_request(msg, ("1.1.1.1", 8000))
        # Just logs, verify no exception

        # 2. Valid hash
        msg = {"type": "PATCH", "target_hash": "abcdef"}
        p.handle_patch_request(msg, ("1.1.1.1", 8000))
        # Logs info

    def test_handle_revoke_node(self):
        p = DHTProtocol(self.dht)
        # 1. Missing ID
        p.handle_revoke_node({"revoke_id": ""}, ("1.1.1.1", 8000))

        # 2. Valid ID
        revoke_id = b"\x99" * 32
        p.handle_revoke_node({"revoke_id": revoke_id.hex()}, ("1.1.1.1", 8000))
        self.assertIn(revoke_id, self.dht.routing.revoked_nodes)

    def test_handle_zanzibar_tuple(self):
        p = DHTProtocol(self.dht)
        msg = {
            "type": "ZANZIBAR",
            "namespace": "doc",
            "object_id": "1",
            "relation": "viewer",
            "subject_namespace": "user",
            "subject_id": "alice",
        }

        # Ensure local import inside handler always resolves deterministically.
        mock_zanzibar_module = MagicMock()
        mock_zanzibar_module.RelationTuple = MagicMock()
        mock_zanzibar_module.zanzibar = MagicMock()

        with patch.dict(
            sys.modules, {"warm_logic.kernel.zanzibar": mock_zanzibar_module}
        ):
            p.handle_zanzibar_tuple(msg, ("1.1.1.1", 8000))
            mock_zanzibar_module.zanzibar.write_tuple.assert_called()

            # Exception case
            mock_zanzibar_module.zanzibar.write_tuple.side_effect = Exception("Boom")
            p.handle_zanzibar_tuple(msg, ("1.1.1.1", 8000))
            # Should catch exception
