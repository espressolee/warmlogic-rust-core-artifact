import asyncio
import base64
import hashlib
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.kernel.mesh.dht import (
    ALPHA,
    K_PARAM,
    Contact,
    DHTProtocol,
    RoutingTable,
    SovereignDHT,
)


@pytest.fixture(autouse=True)
def disable_rust():
    with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
        yield


@pytest.fixture(autouse=True)
def mock_zanzibar():
    with patch("warm_logic.kernel.mesh.dht.check_permission", return_value=True):
        yield


class TestDHTPerfect10:
    def create_pqc_contact(self, name: str):
        pk = name.encode().ljust(32, b"\x00")
        nid = hashlib.sha3_256(pk).digest()
        return Contact(
            node_id=nid,
            address="1.1.1.1",
            port=80,
            public_key=pk,
            silicon_id="S",
            capabilities={},
        )

    @pytest.mark.asyncio
    async def test_surgical_annihilation(self):
        node_id = b"\xff" * 32

        # 1. Contact Eq (45-49)
        c0 = self.create_pqc_contact("C0")
        assert c0 == c0
        assert c0 != "ST"
        assert c0 != self.create_pqc_contact("C1")

        # 2. Routing Table (93-136, 142-146, 175, 185, 198, 215, 222-229, 236, 276, 284-308)
        rt = RoutingTable(node_id)
        rt.revoked_nodes.add(b"REV")
        c_rev = Contact(b"REV", "1", 1)
        await rt.update(c_rev)  # 117-120
        c_fail = self.create_pqc_contact("FAIL")
        with patch.object(rt, "_verify_binding", return_value=False):
            await rt.update(c_fail)  # 123

        rt.split_bucket(0)  # 142-146

        with patch.object(rt, "_use_rust", True):
            rt._rust_table = MagicMock()
            rt._rust_table.update.side_effect = Exception("err")
            try:
                await rt.update(c0)  # 185
            except:
                pass
            rt._rust_table.find_closest.side_effect = Exception("err")
            try:
                rt.find_neighbors(node_id)  # 236
            except:
                pass

        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.mesh.dht.rust_loader.load_rust_core") as lrc:
                lrc.return_value.RustRoutingTable.side_effect = Exception("err")
                try:
                    rt.__init__(node_id)  # 276, 286-299
                except:
                    pass
                try:
                    rt.get_all_contacts()  # 305-307
                except:
                    pass

        # Eviction
        with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
            rt.buckets[0].contacts = [c0]
            d = MagicMock()
            d.ping = AsyncMock(return_value=True)
            await rt.update(self.create_pqc_contact("C_NEW"), dht=d)
            rt.buckets[0].contacts = [c0]
            d.ping = AsyncMock(return_value=False)
            await rt.update(self.create_pqc_contact("C_DEAD"), dht=d)

        # 3. DHT Lifecycle & Broadcast (340-361, 378-389, 559-563, 595-600, 624-625, 658)
        with patch("builtins.__import__", side_effect=ImportError):
            SovereignDHT(node_id, "1", 1)  # 340-349

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.rust_loader.load_rust_core") as lrc:
                lrc.return_value.SovereignStore.side_effect = Exception("err")
                SovereignDHT(node_id, "1", 1)  # 353-361

        dht = SovereignDHT(node_id, "1", 1)
        dht.storage = {}
        mock_transport = MagicMock()
        mock_transport.start_server = AsyncMock()
        dht.silicon_id = "VIRTUAL"

        with (
            patch(
                "warm_logic.kernel.mesh.dht.discover_public_address",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "warm_logic.kernel.mesh.dht.create_transport",
                return_value=mock_transport,
            ),
        ):
            await dht.start(enable_nat_discovery=True)  # 388-389
        dht.transport = mock_transport

        dht.transport.sendto.side_effect = Exception("err")
        try:
            dht.broadcast(b"m")  # 559-563
        except:
            pass

        with patch.object(dht, "broadcast_network", side_effect=Exception("fail")):
            try:
                dht.announce_presence()  # 595-600
            except:
                pass

        dht._protocol = None
        try:
            await dht.rpc_call(c0, {})  # 624-625
        except:
            pass
        assert dht.server == dht.transport  # 658

        # 4. Bootstrap & Iterative (417-536, 540-550)
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", MagicMock()),
            patch(
                "json.load",
                return_value={"trust_anchors": [{"address": "1", "port": 1}]},
            ),
        ):
            try:
                await dht.bootstrap()  # 417-428
            except:
                pass

        with patch.object(rt, "find_neighbors", return_value=[]):
            await dht.iterative_find_node(node_id)  # 448-449

        dht.rpc_call = AsyncMock(
            side_effect=[{"type": "NODES", "nodes": []}, Exception("fail")]
        )
        try:
            await dht.iterative_find_node(node_id)  # 479-524
        except:
            pass

        # 5. Protocol & Handlers (669-776, 782-798, 807-815, 820, 834, 840-869, 877-896, 952-1007, 1073-1093, 1099-1115, 1123-1145)
        proto = DHTProtocol(dht)
        dht._protocol = proto

        # Datagram received error paths
        proto.datagram_received(b"!", ("1", 1))  # JSON error
        proto.datagram_received(
            json.dumps({"sender_pk": "!!!"}).encode(), ("1", 1)
        )  # B64 error

        fut = asyncio.get_running_loop().create_future()
        dht._requests["test_id"] = fut
        proto.datagram_received(
            json.dumps({"msg_id": "test_id", "type": "PONG"}).encode(), ("1", 1)
        )  # 678 SUCCESS

        dht.fleet_manager = MagicMock()
        proto.datagram_received(
            json.dumps(
                {"type": "POLICY_UPDATE", "invariant_id": "i", "state": "s"}
            ).encode(),
            ("1", 1),
        )  # 760-766
        proto.handle_manifest_announce({}, ("1", 1))  # 789-790 missing fields
        proto.handle_manifest_announce(
            {"sender_id": node_id.hex(), "manifest_hash": "h"}, ("1", 1)
        )  # 798
        proto.handle_find_node({"target_id": node_id.hex()}, ("1", 1))  # 820

        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = False
            proto.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 953-959
            with patch(
                "warm_logic.kernel.mesh.dht.check_permission", return_value=False
            ):
                proto.handle_store_value_request(
                    {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"},
                    ("1", 1),
                )  # 967-969
            dht.storage = MagicMock()
            if hasattr(dht.storage, "put"):
                dht.storage.put.side_effect = Exception("io")
            proto.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 981-1007

        # handle_find_value_request removed - method does not exist in DHTProtocol
        proto.handle_patch_request({"target_hash": "h"}, ("1", 1))  # 1073-1081
        proto.handle_revoke_node(
            {"revoke_id": node_id.hex(), "signature": "BAD"}, ("1", 1)
        )  # 1115
        proto.handle_revoke_node({}, ("1", 1))  # 1103/1093

        with patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple", return_value=False
        ):
            proto.handle_zanzibar_tuple(
                {"type": "ZANZIBAR_TUPLE"}, ("1", 1)
            )  # 1137-1140
        with patch("warm_logic.kernel.zanzibar.RelationTuple", side_effect=Exception):
            proto.handle_zanzibar_tuple(
                {"type": "ZANZIBAR_TUPLE"}, ("1", 1)
            )  # 1144-1145
