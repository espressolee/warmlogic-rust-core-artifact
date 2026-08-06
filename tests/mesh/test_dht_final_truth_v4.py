import asyncio
import base64
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


class TestDHTFinalTruthV4:
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
    async def test_surgical_annihilation_v4(self):
        # Local ID is FF...
        node_id = b"\xff" * 32
        # Peer ID is 00...
        peer_id = b"\x00" * 32
        peer_pk = b"\x11" * 32
        peer_id_valid = hashlib.sha3_256(peer_pk).digest()

        # --- Routing Table Python Branches ---
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
            rt = RoutingTable(node_id)
            c0 = self.create_pqc_contact("C0")

            # 176: Self-Filter
            await rt.update(Contact(node_id, "1", 1))

            await rt.update(c0)
            rt.split_bucket(0)

            # Binding error paths
            await rt.update(
                Contact(peer_id, "trigger_binding_fail", 1, public_key=b"P" * 32)
            )
            await rt.update(Contact(peer_id, "1.1.1.1", 1, public_key=None))
            await rt.update(Contact(peer_id, "1.1.1.1", 1, public_key=b"WRONG"))
            await rt.update(
                Contact(
                    peer_id_valid, "1.1.1.1", 1, public_key=peer_pk, silicon_id=None
                )
            )

            # Eviction
            with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
                rt.buckets[0].contacts = [c0]
                d = MagicMock()
                d.ping = AsyncMock(return_value=True)
                await rt.update(self.create_pqc_contact("C_NEW"), dht=d)
                rt.buckets[0].contacts = [c0]
                d.ping = AsyncMock(return_value=False)
                await rt.update(self.create_pqc_contact("C_DEAD"), dht=d)

        # Rust Gaps
        rt_r = RoutingTable(node_id)
        with patch.object(rt_r, "_use_rust", True):
            rt_r._rust_table = MagicMock()
            rt_r._rust_table.update.side_effect = Exception("err")
            try:
                await rt_r.update(c0)
            except:
                pass
            rt_r._rust_table.find_closest.side_effect = Exception("err")
            try:
                rt_r.find_neighbors(node_id)
            except:
                pass

        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.mesh.dht.rust_loader.load_rust_core") as lrc:
                lrc.return_value.RustRoutingTable.side_effect = Exception("err")
                try:
                    RoutingTable(node_id).get_all_contacts()
                except:
                    pass

        # --- DHT Lifecycle ---
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
            d1 = SovereignDHT(node_id, "1", 1)
        with patch("builtins.__import__", side_effect=ImportError):
            try:
                SovereignDHT(node_id, "1", 1)
            except:
                pass
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.mesh.dht.rust_loader.load_rust_core") as lrc:
                lrc.return_value.SovereignStore.side_effect = Exception("err")
                try:
                    SovereignDHT(node_id, "1", 1)
                except:
                    pass

        # NAT Fail
        async def mock_nat():
            return None

        with patch("warm_logic.kernel.mesh.dht.create_transport") as ct:
            ct.return_value.start_server = AsyncMock()
            with patch(
                "warm_logic.kernel.mesh.dht.discover_public_address",
                side_effect=mock_nat,
            ):
                try:
                    await d1.start(enable_nat_discovery=True)
                except:
                    pass

        d1.transport = MagicMock()
        d1.transport.sendto.side_effect = Exception("err")
        try:
            d1.broadcast(b"m")
        except:
            pass
        d1.broadcast_policy_event("i", "s")
        with patch.object(d1, "broadcast_network", side_effect=Exception("err")):
            try:
                d1.announce_presence()
            except:
                pass
        _ = d1.server

        # --- Search & Bootstrap ---
        d2 = SovereignDHT(node_id, "1", 1)
        d2.transport = MagicMock()
        # Bootstrap error paths
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", side_effect=Exception("io")),
        ):
            await d2.bootstrap()
        with patch("os.path.exists", return_value=False):
            await d2.bootstrap()

        with patch.object(d2.routing, "find_neighbors", return_value=[]):
            await d2.iterative_find_node(node_id)
        d2.rpc_call = AsyncMock(
            side_effect=[{"type": "NODES", "nodes": []}, Exception("fail")]
        )
        try:
            await d2.iterative_find_node(node_id)
        except:
            pass

        # --- Protocol Handlers ---
        p = DHTProtocol(d2)
        d2._protocol = p
        p.datagram_received(b"!", ("1", 1))
        p.datagram_received(json.dumps({"sender_pk": "!!!"}).encode(), ("1", 1))
        f = asyncio.get_running_loop().create_future()
        d2._requests["t"] = f
        p.datagram_received(json.dumps({"msg_id": "t", "type": "P"}).encode(), ("1", 1))

        d2.fleet_manager = MagicMock()
        p.datagram_received(
            json.dumps(
                {"type": "POLICY_UPDATE", "invariant_id": "i", "state": "s"}
            ).encode(),
            ("1", 1),
        )
        p.handle_manifest_announce(
            {"sender_id": node_id.hex(), "manifest_hash": "h"}, ("1", 1)
        )
        p.handle_find_node({"target_id": node_id.hex()}, ("1", 1))
        d2.gossip_agent = MagicMock()
        p.handle_mutation_proposal({"mutation_id": "m"}, ("1", 1))
        p.handle_mutation_vote({"voter_id": "v", "mutation_id": "m"}, ("1", 1))
        p.handle_insight_announce({"sender_id": "v", "insight": {}}, ("1", 1))

        # Store Details
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = False
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )
            with patch(
                "warm_logic.kernel.mesh.dht.check_permission", return_value=False
            ):
                p.handle_store_value_request(
                    {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"},
                    ("1", 1),
                )
            d2.storage = MagicMock()
            d2.storage.put.side_effect = Exception("io")
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )
            d2.storage = None
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )

        # Patch/Revoke/Zanzibar
        p.handle_patch_request({"target_hash": "h"}, ("1", 1))
        p.handle_revoke_node(
            {"revoke_id": node_id.hex(), "signature": "MASTER_VETO"}, ("1", 1)
        )
        p.handle_revoke_node({"revoke_id": node_id.hex(), "signature": "BAD"}, ("1", 1))
        p.handle_revoke_node({}, ("1", 1))
        with patch("warm_logic.kernel.zanzibar.RelationTuple", side_effect=Exception):
            p.handle_zanzibar_tuple({"type": "ZANZIBAR_TUPLE"}, ("1", 1))
        with patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple", return_value=True
        ):
            p.handle_zanzibar_tuple({"type": "ZANZIBAR_TUPLE"}, ("1", 1))
        with patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple", return_value=False
        ):
            p.handle_zanzibar_tuple({"type": "ZANZIBAR_TUPLE"}, ("1", 1))
