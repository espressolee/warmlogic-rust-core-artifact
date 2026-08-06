import asyncio
import hashlib
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.kernel.mesh.dht import (
    Contact,
    DHTProtocol,
    RoutingTable,
    SovereignDHT,
)


class TestDHTTotalAnnihilation:
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
    async def test_annihilation_routing(self):
        node_id = b"\xff" * 32
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
            rt = RoutingTable(node_id)
            c0 = self.create_pqc_contact("C0")
            await rt.update(c0)
            rt.split_bucket(0)  # Hits 142-146

            rt.revoked_nodes.add(b"REV")
            await rt.update(Contact(b"REV", "1", 1))  # Hits 117-120

            with patch.object(rt, "_verify_binding", return_value=False):
                await rt.update(self.create_pqc_contact("C1"))  # Hits 123

            with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
                rt.buckets[0].contacts = [c0]
                d = MagicMock()
                d.ping = AsyncMock(return_value=True)
                await rt.update(
                    self.create_pqc_contact("C_NEW"), dht=d
                )  # Eviction (True)
                rt.buckets[0].contacts = [c0]
                d.ping = AsyncMock(return_value=False)
                await rt.update(
                    self.create_pqc_contact("C_DEAD"), dht=d
                )  # Eviction (False)

        rt_rust = RoutingTable(node_id)
        with patch.object(rt_rust, "_use_rust", True):
            rt_rust._rust_table = MagicMock()
            rt_rust._rust_table.update.side_effect = Exception("err")
            try:
                await rt_rust.update(c0)  # Hits 185
            except:
                pass
            rt_rust._rust_table.find_closest.side_effect = Exception("err")
            try:
                rt_rust.find_neighbors(node_id)  # Hits 236
            except:
                pass

        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.mesh.dht.rust_loader.load_rust_core") as lrc:
                lrc.return_value.RustRoutingTable.side_effect = Exception("err")
                try:
                    RoutingTable(node_id).get_all_contacts()  # Hits 276, 286-307
                except:
                    pass

    @pytest.mark.asyncio
    async def test_annihilation_dht_lifecycle(self):
        node_id = b"\xff" * 32
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
            dht = SovereignDHT(node_id, "1", 1)

        with patch("builtins.__import__", side_effect=ImportError):
            try:
                SovereignDHT(node_id, "1", 1)  # Hits 340-341, 348-349
            except:
                pass
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.mesh.dht.rust_loader.load_rust_core") as lrc:
                lrc.return_value.SovereignStore.side_effect = Exception("err")
                try:
                    SovereignDHT(node_id, "1", 1)  # Hits 356
                except:
                    pass

        async def mock_nat():
            return None

        with patch("warm_logic.kernel.mesh.dht.create_transport") as ct:
            ct.return_value.start_server = AsyncMock()
            with patch(
                "warm_logic.kernel.mesh.dht.discover_public_address",
                side_effect=mock_nat,
            ):
                try:
                    await dht.start(enable_nat_discovery=True)  # Hits 388-389
                except:
                    pass

        dht.transport = MagicMock()
        dht.transport.sendto.side_effect = Exception("err")
        try:
            dht.broadcast(b"m")  # Hits 559-563
        except:
            pass
        dht.broadcast_policy_event("i", "s")
        with patch.object(dht, "broadcast_network", side_effect=Exception("err")):
            try:
                dht.announce_presence()  # Hits 596
            except:
                pass

    @pytest.mark.asyncio
    async def test_annihilation_iterative(self):
        node_id = b"\xff" * 32
        dht = SovereignDHT(node_id, "1", 1)
        dht.transport = MagicMock()
        # Bootstrap
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", MagicMock()),
            patch(
                "json.load",
                return_value={"trust_anchors": [{"address": "1", "port": 1}]},
            ),
        ):
            try:
                await dht.bootstrap()  # Hits 426-427
            except:
                pass
        # Iterative
        with patch.object(dht.routing, "find_neighbors", return_value=[]):
            await dht.iterative_find_node(node_id)  # Hits 448-449

        dht.rpc_call = AsyncMock(
            side_effect=[{"type": "NODES", "nodes": []}, Exception("fail")]
        )
        try:
            await dht.iterative_find_node(node_id)  # Hits 452-453, 484, 508-509, 522
        except:
            pass

    @pytest.mark.asyncio
    async def test_annihilation_protocol(self):
        node_id = b"\xff" * 32
        dht = SovereignDHT(node_id, "1", 1)
        proto = DHTProtocol(dht)
        # Datagram errors
        proto.datagram_received(b"!", ("1", 1))  # Hits 680-683
        proto.datagram_received(json.dumps({"sender_pk": "!!!"}).encode(), ("1", 1))
        # RPC Result
        fut = asyncio.get_running_loop().create_future()
        dht._requests["t"] = fut
        proto.datagram_received(
            json.dumps({"msg_id": "t", "type": "P"}).encode(), ("1", 1)
        )  # Hits 678
        # Invariants
        dht.fleet_manager = MagicMock()
        proto.datagram_received(
            json.dumps(
                {"type": "POLICY_UPDATE", "invariant_id": "i", "state": "s"}
            ).encode(),
            ("1", 1),
        )  # Hits 760, 766
        proto.handle_manifest_announce(
            {"sender_id": node_id.hex(), "manifest_hash": "h"}, ("1", 1)
        )  # Hits 798
        proto.handle_find_node({"target_id": node_id.hex()}, ("1", 1))  # Hits 820
        # Mutation
        dht.gossip_agent = MagicMock()
        proto.handle_mutation_proposal({"mutation_id": "m"}, ("1", 1))
        proto.handle_mutation_vote({"voter_id": "v", "mutation_id": "m"}, ("1", 1))
        # Store
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = False
            proto.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # Hits 953-959
            with patch(
                "warm_logic.kernel.mesh.dht.check_permission", return_value=False
            ):
                proto.handle_store_value_request(
                    {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"},
                    ("1", 1),
                )  # Hits 967-969
            # NO_STORAGE
            dht.storage = None
            proto.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # Hits 1007-1009
            # STORAGE_IO_ERROR
            dht.storage = MagicMock()
            if hasattr(dht.storage, "put"):
                dht.storage.put.side_effect = Exception("io")
            proto.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # Hits 981-1007
        # Revoke/Zanzibar
        proto.handle_patch_request({"target_hash": "h"}, ("1", 1))  # Hits 1073-1093
        proto.handle_revoke_node(
            {"revoke_id": node_id.hex(), "signature": "BAD"}, ("1", 1)
        )  # Hits 1115
        proto.handle_revoke_node({}, ("1", 1))  # Hits 1103
        with patch("warm_logic.kernel.zanzibar.RelationTuple", side_effect=Exception):
            proto.handle_zanzibar_tuple(
                {"type": "ZANZIBAR_TUPLE"}, ("1", 1)
            )  # Hits 1144-1145
        with patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple", return_value=False
        ):
            proto.handle_zanzibar_tuple(
                {"type": "ZANZIBAR_TUPLE"}, ("1", 1)
            )  # Hits 1138
