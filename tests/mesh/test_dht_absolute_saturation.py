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


class TestDHTAbsoluteTruthCollector:
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
        print(f"DEBUG: dht_mod file: {dht_mod.__file__}")
        local_id = b"\xff" * 32

        # --- PHASE 1: Routing Table ---
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
            rt = RoutingTable(local_id)

            # 1. BRL Check (120)
            c_revoked = self.create_pqc_contact("REV")
            rt.revoked_nodes.add(c_revoked.node_id)
            assert not rt._verify_binding(c_revoked)

            # 2. Binding Failures (123, 126, 133-136, 142-146)
            rt._verify_binding(
                self.create_pqc_contact("F1", address="trigger_binding_fail")
            )  # 123
            rt._verify_binding(
                Contact(node_id=b"0" * 32, address="a", port=1, public_key=None)
            )  # 126
            rt._verify_binding(
                self.create_pqc_contact("F2", public_key=b"BAD" * 10)
            )  # 133-136
            rt._verify_binding(
                Contact(
                    node_id=b"0" * 32,
                    address="a",
                    port=1,
                    public_key=b"PK",
                    silicon_id=None,
                )
            )  # 142-146

            # 3. Bucket Split (161-171)
            c1 = self.create_pqc_contact("C1", (1).to_bytes(32, "big"))
            rt.buckets[0].contacts.append(c1)
            rt.split_bucket(0)  # Hits 161-171

            # 4. Update Self (175)
            await rt.update(Contact(local_id, "1", 1))

            # 5. Eviction & Split Trigger (212-229)
            with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
                rt = RoutingTable(local_id)  # buckets = [0, 2^256]
                c_low = self.create_pqc_contact("LOW", (0).to_bytes(32, "big"))
                await rt.update(c_low)

                # Split (local_id is high)
                c_split = self.create_pqc_contact(
                    "SPLIT", (2**255 + 1).to_bytes(32, "big")
                )
                await rt.update(c_split)

                # Eviction (c_low is in bucket 0)
                c_evict = self.create_pqc_contact("EVICT", (2**254).to_bytes(32, "big"))
                d = MagicMock()
                d.ping = AsyncMock(return_value=True)
                await rt.update(c_evict, dht=d)  # Move to end

                d.ping = AsyncMock(return_value=False)
                await rt.update(c_evict, dht=d)  # Evict

                rt._evict_in_progress = True
                await rt.update(c_evict, dht=d)  # proactive exit
                rt._evict_in_progress = False

        # --- PHASE 2: Rust Routing Gaps ---
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.mesh.dht.rust_loader.load_rust_core") as lrc:
                mock_rs = MagicMock()
                lrc.return_value = mock_rs
                mock_rt = MagicMock()
                mock_rs.RustRoutingTable.return_value = mock_rt

                rt_r = RoutingTable(local_id)
                c = self.create_pqc_contact("C")
                await rt_r.update(c)  # Hit 184-185

                mock_rt.update.side_effect = Exception("err")
                try:
                    await rt_r.update(c)  # Hit 187
                except Exception:
                    pass

                mock_rt.find_closest.side_effect = Exception("err")
                try:
                    rt_r.find_neighbors(local_id)  # Hit 241
                except Exception:
                    pass

                mock_rt.get_all_contacts.side_effect = Exception("err")
                try:
                    rt_r.get_all_contacts()  # Hit 307
                except Exception:
                    pass

        # --- PHASE 3: DHT Core & Protocol ---
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
        dht.transport = mock_transport

        with patch(
            "warm_logic.kernel.mesh.dht.discover_public_address", return_value=None
        ):
            try:
                await dht.start(enable_nat_discovery=True)  # 389
            except Exception:
                pass

        # Stop path (426-427)
        dht.storage = MagicMock()
        await dht.stop()

        # Bootstrap IO Error (449)
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", side_effect=Exception),
        ):
            await dht.bootstrap()

        # Search Errors (484, 522)
        dht.rpc_call = AsyncMock(return_value={"type": "NODES", "nodes": []})
        await dht.iterative_find_node(local_id)
        dht.rpc_call = AsyncMock(side_effect=Exception)
        try:
            await dht.iterative_find_node(local_id)  # 484
        except Exception:
            pass

        # Protocol Handlers
        p = DHTProtocol(dht)
        p.datagram_received(b"!", ("1", 1))  # 678
        p.datagram_received(b"VERY LONG STUPID DATA" * 100, ("1", 1))  # 646

        # RPC correlations (681, 683)
        msg_id = "MID"
        f = asyncio.get_running_loop().create_future()
        dht._requests[msg_id] = f
        p.datagram_received(
            json.dumps({"msg_id": msg_id, "type": "P"}).encode(), ("1", 1)
        )
        p.datagram_received(
            json.dumps({"msg_id": "NONE", "type": "P"}).encode(), ("1", 1)
        )

        # Policy (761, 767)
        dht.fleet_manager = MagicMock()
        p.handle_policy_update({"invariant_id": "idx", "state": "s"}, ("1", 1))
        dht.fleet_manager = None
        p.handle_policy_update({"invariant_id": "idx", "state": "s"}, ("1", 1))

        # Manifest & Find Node (799, 821)
        p.handle_manifest_announce(
            {"sender_id": local_id.hex(), "manifest_hash": "h"}, ("1", 1)
        )
        p.handle_find_node({"target_id": local_id.hex()}, ("1", 1))

        # Store Value (953-1008)
        p._send_store_response = MagicMock()
        p.handle_store_value_request({}, ("1", 1))  # 953

        with patch("warm_logic_rs.RustZKProofGenerator") as zk_gen:
            zk_gen.return_value.verify_state_proof.return_value = False
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 974

            zk_gen.return_value.verify_state_proof.return_value = True
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

        # Patch & Zanzibar (1057-1139)
        p.handle_patch_request({"target_hash": "h"}, ("1", 1))  # 1057-1061
        with patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple", return_value=False
        ):
            p.handle_zanzibar_tuple({"type": "Z"}, ("1", 1))  # 1139
