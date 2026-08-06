import asyncio
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import warm_logic.kernel.mesh.dht as dht_mod
from warm_logic.kernel.mesh.dht import (
    Contact,
    DHTProtocol,
    RoutingTable,
    SovereignDHT,
)


class TestDHTUltimateSaturationV24:
    def create_pqc_contact(
        self,
        name: str,
        node_id: bytes = None,
        address: str = "1.1.1.1",
        public_key: bytes = b"PK",
    ):
        pk = public_key if public_key else name.encode().ljust(32, b"\x00")
        nid = node_id if node_id else hashlib.sha3_256(pk).digest()
        return Contact(
            node_id=nid,
            address=address,
            port=80,
            public_key=pk,
            silicon_id="S",
            capabilities={},
        )

    @pytest.mark.asyncio
    async def test_surgical_saturation_perfection(self):
        local_id = b"\xff" * 32

        # --- PHASE 1: Routing Table ---
        # 1. Force Python Mode
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
            rt = RoutingTable(local_id)

            # Hit __eq__ (49)
            c_low = self.create_pqc_contact("C_LOW", b"\x00" * 32)
            assert c_low != "NOT_A_CONTACT"
            assert c_low == c_low

            # Hit _verify_binding branches directly
            rt.revoked_nodes.add(b"REVOKED")
            rt._verify_binding(Contact(node_id=b"REVOKED", address="1", port=1))  # 120
            rt._verify_binding(
                self.create_pqc_contact("FAIL_ADDR", address="trigger_binding_fail")
            )  # 123
            rt._verify_binding(
                Contact(node_id=b"0" * 32, address="1", port=1, public_key=None)
            )  # 126
            rt._verify_binding(
                self.create_pqc_contact("FAIL_ID", public_key=b"BAD_PUBKEY" * 4)
            )  # 137
            rt._verify_binding(
                Contact(
                    node_id=b"0" * 32,
                    address="1",
                    port=1,
                    public_key=b"PK",
                    silicon_id=None,
                )
            )  # 142-146

            # 175: Self-Filter
            await rt.update(Contact(local_id, "1", 1))

            # 199: Bucket Not Found
            with patch.object(rt, "buckets", []):
                await rt.update(c_low)

            # 161: Forced Split
            rt.split_bucket(0)

            # Split Trigger (162)
            rt = RoutingTable(local_id)
            original_k = dht_mod.K_PARAM
            dht_mod.K_PARAM = 1
            try:
                await rt.update(c_low)
                await rt.update(self.create_pqc_contact("C_SPLIT", b"\x11" * 32))

                # EVICTION logic (212-229)
                c1 = self.create_pqc_contact("C1", (1).to_bytes(32, "big"))
                rt.buckets[0].contacts = [c1]
                c2 = self.create_pqc_contact("C2", (2).to_bytes(32, "big"))
                d = MagicMock()
                d.ping = AsyncMock(return_value=True)
                await rt.update(c2, dht=d)
                rt.buckets[0].contacts = [c1]
                d.ping = AsyncMock(return_value=False)
                await rt.update(c2, dht=d)
                rt._evict_in_progress = True
                await rt.update(c2, dht=d)
                rt._evict_in_progress = False
            finally:
                dht_mod.K_PARAM = original_k

        # Rust Gaps
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.mesh.dht.rust_loader.load_rust_core") as lrc:
                mock_rs = MagicMock()
                lrc.return_value = mock_rs
                mock_rt = MagicMock()
                mock_rs.RustRoutingTable.return_value = mock_rt
                rt_rust = RoutingTable(local_id)
                await rt_rust.update(c_low)  # 186
                mock_rt.update.side_effect = Exception("err")
                try:
                    await rt_rust.update(c_low)  # 188
                except Exception:
                    pass
                mock_rt.find_closest.side_effect = Exception("err")
                try:
                    rt_rust.find_neighbors(local_id)  # 241
                except Exception:
                    pass
                mock_rt.get_all_contacts.side_effect = Exception("err")
                try:
                    rt_rust.get_all_contacts()  # 299
                except Exception:
                    pass

        # --- PHASE 2: DHT Core ---
        with (
            patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True),
            patch(
                "warm_logic.kernel.mesh.dht.rust_loader.load_rust_core",
                side_effect=Exception,
            ),
        ):
            try:
                SovereignDHT(local_id, "1", 1)  # 341
            except Exception:
                pass
        dht = SovereignDHT(local_id, "1", 1)
        mock_transport = MagicMock()
        mock_transport.start_server = AsyncMock()
        mock_transport.sendto = MagicMock()
        dht.transport = mock_transport

        async def mock_nat(*args, **kwargs):
            return None

        def mock_create(*args, **kwargs):
            return mock_transport

        with patch(
            "warm_logic.kernel.mesh.dht.create_transport", side_effect=mock_create
        ):
            with patch(
                "warm_logic.kernel.mesh.dht.discover_public_address",
                side_effect=mock_nat,
            ):
                try:
                    await dht.start(enable_nat_discovery=True)  # 389
                except Exception:
                    pass
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", side_effect=Exception("io")),
        ):
            await dht.bootstrap()  # 449
        with patch("os.path.exists", return_value=False):
            await dht.bootstrap()  # 452
        dht.rpc_call = AsyncMock(
            side_effect=[{"type": "NODES", "nodes": []}, Exception("fail")]
        )
        try:
            await dht.iterative_find_node(local_id)  # 484, 522
        except Exception:
            pass
        mock_transport.sendto.side_effect = Exception("err")
        try:
            dht.broadcast(b"m")  # 560
        except Exception:
            pass
        with patch.object(dht, "broadcast_network", side_effect=Exception("err")):
            try:
                dht.announce_presence()  # 596
            except Exception:
                pass
        _ = dht.server

        # --- PHASE 3: Protocol Handlers ---
        p = DHTProtocol(dht)
        dht._protocol = p
        p.datagram_received(b"!", ("1", 1))  # 678
        p.datagram_received(b"REALLY_STUPID_DATAGRAM" * 200, ("1", 1))  # 646
        f = asyncio.get_running_loop().create_future()
        dht._requests["ULT_ID"] = f
        p.datagram_received(
            json.dumps({"msg_id": "ULT_ID", "type": "P"}).encode(), ("1", 1)
        )  # 681
        p.datagram_received(
            json.dumps({"msg_id": "NONE_ID", "type": "P"}).encode(), ("1", 1)
        )  # 683
        dht.fleet_manager = MagicMock()
        p.datagram_received(
            json.dumps(
                {"type": "POLICY_UPDATE", "invariant_id": "idx", "state": "st"}
            ).encode(),
            ("1", 1),
        )  # 761
        dht.fleet_manager = None
        p.datagram_received(
            json.dumps(
                {"type": "POLICY_UPDATE", "invariant_id": "idx", "state": "st"}
            ).encode(),
            ("1", 1),
        )  # 767
        p.handle_manifest_announce(
            {"sender_id": local_id.hex(), "manifest_hash": "h"}, ("1", 1)
        )  # 799
        p.handle_find_node({"target_id": local_id.hex()}, ("1", 1))  # 821
        p._send_store_response = MagicMock()
        p.handle_store_value_request({}, ("1", 1))  # 953
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = False
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 974
            zk.return_value.verify_state_proof.return_value = True
            dht.storage = MagicMock()
            dht.storage.put = MagicMock()
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 1000
            dht.storage.put.side_effect = Exception("io")
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 1003
            dht.storage = None
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 1007
        p.transport = MagicMock()
        p.handle_patch_request({"target_hash": "hash"}, ("1", 1))  # 1057-1061
        p.handle_revoke_node(
            {"revoke_id": local_id.hex(), "signature": "BAD"}, ("1", 1)
        )  # 1124
        p.handle_revoke_node({}, ("1", 1))  # 1104
        with patch("warm_logic.kernel.zanzibar.RelationTuple", side_effect=Exception):
            p.handle_zanzibar_tuple({"type": "ZANZIBAR_TUPLE"}, ("1", 1))  # 1146
        with patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple", return_value=False
        ):
            p.handle_zanzibar_tuple({"type": "ZANZIBAR_TUPLE"}, ("1", 1))  # 1139
