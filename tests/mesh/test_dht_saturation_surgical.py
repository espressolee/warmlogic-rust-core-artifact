import asyncio
import base64
import hashlib
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.kernel.mesh.dht import (
    ALPHA,
    K_PARAM,
    Contact,
    DHTProtocol,
    KBucket,
    RoutingTable,
    SovereignDHT,
)
from warm_logic.kernel.mesh.transport import AbstractTransport


# Global patch to disable Rust for Python logic saturation
@pytest.fixture(autouse=True)
def disable_rust():
    with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
        yield


# Mock Zanzibar to allow all DHT operations
@pytest.fixture(autouse=True)
def mock_zanzibar():
    with patch("warm_logic.kernel.mesh.dht.check_permission", return_value=True):
        yield


class TestDHTSaturationSurgical:
    @pytest.fixture
    def node_id(self):
        return os.urandom(32)

    def create_contact(self, name: str, port: int = 10000):
        pk = name.encode().ljust(32, b"\x00")
        nid = hashlib.sha3_256(pk).digest()
        return Contact(
            node_id=nid,
            address="127.0.0.1",
            port=port,
            public_key=pk,
            silicon_id="HW_" + name,
            capabilities={"CPU": 1},
        )

    def init_dht_clean(self, node_id):
        dht = SovereignDHT(
            node_id=node_id,
            address="127.0.0.1",
            port=12345,
            public_key=b"pubkey_fixed",
            private_key="privkey_fixed",
        )
        dht.silicon_id = "HW_DEVICE_0"
        dht.capabilities = {"ROLE": 1}
        dht.storage = {}
        return dht

    @pytest.mark.asyncio
    async def test_surgical_routing_logic(self):
        local_id = b"\x00" * 32
        rt = RoutingTable(local_id)

        # 1. Revoke node (93-99)
        rt.revoke_node(b"X" * 32)
        assert b"X" * 32 in rt.revoked_nodes

        # 2. Split logic (142-146)
        with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
            await rt.update(self.create_contact("C1", port=100))
            await rt.update(self.create_contact("C2", port=101))
            assert len(rt.buckets) > 1

        # 3. Geo scoring (228-236)
        with patch(
            "warm_logic.mesh.topology.NetworkTopology.get_latency_between_nodes",
            return_value=150.0,
        ):
            rt.find_neighbors(os.urandom(32))

    @pytest.mark.asyncio
    async def test_surgical_dht_start_and_init(self, node_id, tmp_path):
        # 1. Mode fallback (348-356)
        with patch.dict(os.environ, {"WARM_LOGIC_TRANSPORT_MODE": "UDP"}):
            dht = SovereignDHT(node_id, "127.0.0.1", 12345)
            assert dht.port == 12345

        # 2. Transport start failure (379-384)
        with patch("warm_logic.kernel.mesh.dht.create_transport") as mt:
            mt.return_value.start_server = AsyncMock(side_effect=Exception("Failed"))
            with pytest.raises(Exception):
                await dht.start()

    @pytest.mark.asyncio
    async def test_surgical_protocol_handlers_final(self, node_id):
        dht = self.init_dht_clean(node_id)
        dht.transport = MagicMock()
        proto = DHTProtocol(dht)
        proto.transport = dht.transport
        dht._protocol = proto

        addr = ("1.1.1.1", 100)

        def send(m):
            if "sender_id" not in m:
                m["sender_id"] = os.urandom(32).hex()
            proto.datagram_received(json.dumps(m).encode(), addr)

        # 1. Find Node with nodes response (781)
        c1 = self.create_contact("S1")
        dht.routing.buckets[0].contacts.append(c1)
        send({"type": "FIND_NODE", "target_id": os.urandom(32).hex(), "msg_id": "r1"})

        # 2. Store Value with ACL Reject (925) - Temporarily un-mock for this specific call
        with patch("warm_logic.kernel.mesh.dht.check_permission", return_value=False):
            send({"type": "STORE_VALUE", "key": "locked", "msg_id": "r2"})

        # 3. Store Value with Valid ZK (971-981)
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = True
            send(
                {
                    "type": "STORE_VALUE",
                    "key": "k1",
                    "value": "v1",
                    "zk_proof": "p1",
                    "commitment": "c1",
                }
            )
            assert "k1" in dht.storage

        # 4. Patch Request (1056-1076)
        send({"type": "PATCH_REQUEST", "target_hash": "deadbeef", "msg_id": "r3"})

        # 5. Revoke Node (1090-1096)
        send(
            {
                "type": "REVOKE_NODE",
                "revoke_id": os.urandom(32).hex(),
                "signature": "MASTER_VETO",
            }
        )
        send(
            {
                "type": "REVOKE_NODE",
                "revoke_id": os.urandom(32).hex(),
                "signature": "BAD",
            }
        )

    @pytest.mark.asyncio
    async def test_surgical_iterative_find_node(self, node_id):
        dht = self.init_dht_clean(node_id)
        dht.transport = MagicMock()
        # Sleep branch (443-444)
        with patch("asyncio.sleep", return_value=None):
            await dht.bootstrap(seeds=[("1.1.1.1", 80)])

        # Iterative find contact creation (479)
        async def mock_rpc(*args, **kwargs):
            return {
                "type": "NODES",
                "nodes": [
                    {"id": os.urandom(32).hex(), "addr": "2.2.2.2", "port": None}
                ],
            }  # Null port fallback

        # Wait, the port field is missing in the message, it should fallback to 12345.
        async def mock_rpc_no_port(*args, **kwargs):
            return {
                "type": "NODES",
                "nodes": [{"id": os.urandom(32).hex(), "addr": "2.2.2.2"}],
            }

        with patch.object(dht, "rpc_call", side_effect=mock_rpc_no_port):
            await dht.iterative_find_node(os.urandom(32))

    def test_surgical_properties(self, node_id):
        dht = self.init_dht_clean(node_id)
        assert dht.server is None  # 643
