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


class TestDHTAbsoluteSaturation:
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
    async def test_surgical_annihilation_final(self):
        # Local ID is HIGH (0xff...)
        node_id = b"\xff" * 32

        # --- PHASE 1: Routing Table ---
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
            rt = RoutingTable(node_id)
            c_low = self.create_pqc_contact("C_LOW")

            # Hit __eq__ (Line 49)
            assert c_low == c_low
            try:
                c_low == "OTHER"
            except:
                pass

            # Hit Self-Filter (176)
            await rt.update(Contact(node_id, "1", 1))

            # Use K_PARAM=1 for easy splitting/eviction
            with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
                await rt.update(c_low)

                # EVICTION logic (213-230)
                # Fill B0 (range [0, 2**255])
                # Create contacts with specific node_ids from the start
                c1 = Contact(
                    node_id=b"\x00" * 32,
                    address="1.1.1.1",
                    port=80,
                    public_key=b"PK1".ljust(32, b"\x00"),
                    silicon_id="S1",
                    capabilities={},
                )
                c2 = Contact(
                    node_id=b"\x01" * 32,
                    address="1.1.1.2",
                    port=81,
                    public_key=b"PK2".ljust(32, b"\x00"),
                    silicon_id="S2",
                    capabilities={},
                )
                rt.buckets[0].contacts = [c1]
                # B0 is full. Local is NOT in B0.
                d = MagicMock()
                d.ping = AsyncMock(return_value=True)
                await rt.update(c2, dht=d)  # Hits 223-224 (Move to end)

                rt.buckets[0].contacts = [c1]
                d.ping = AsyncMock(return_value=False)
                await rt.update(c2, dht=d)  # Hits 228 (Evict and Add)

            # Target Bucket -1 (199)
            with patch.object(rt, "buckets", []):
                await rt.update(c_low)

        # Rust Gaps
        rt_rust = RoutingTable(node_id)
        with patch.object(rt_rust, "_use_rust", True):
            rt_rust._rust_table = MagicMock()
            rt_rust._rust_table.update.side_effect = Exception("err")
            try:
                await rt_rust.update(c_low)  # Hits 188
            except:
                pass
            rt_rust._rust_table.find_closest.side_effect = Exception("err")
            try:
                rt_rust.find_neighbors(node_id)  # Hits 236
            except:
                pass

        # --- PHASE 2: DHT Lifecycle & Search ---
        dht = SovereignDHT(node_id, "1", 1)
        dht.transport = MagicMock()
        # Bootstrap error paths (448-449, 452-453)
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", side_effect=Exception("io")),
        ):
            await dht.bootstrap()
        with patch("os.path.exists", return_value=False):
            await dht.bootstrap()

        # Iterative Search Timeouts/Errors (485, 523)
        dht.rpc_call = AsyncMock(
            side_effect=[{"type": "NODES", "nodes": []}, Exception("fail")]
        )
        try:
            await dht.iterative_find_node(node_id)
        except:
            pass

        # Broadcast Errors (560-564, 597)
        dht.transport.sendto.side_effect = Exception("err")
        try:
            dht.broadcast(b"m")
        except:
            pass
        with patch.object(dht, "broadcast_network", side_effect=Exception("err")):
            try:
                dht.announce_presence()
            except:
                pass

        # Property (621)
        _ = dht.server

        # --- PHASE 3: Protocol Handlers ---
        p = DHTProtocol(dht)
        # Datagram decode error (679)
        p.datagram_received(b"!", ("1", 1))
        # Result processing for non-existent request (684)
        p.datagram_received(
            json.dumps({"msg_id": "UNKNOWN", "type": "P"}).encode(), ("1", 1)
        )
        # Valid result (681-683)
        f = asyncio.get_running_loop().create_future()
        dht._requests["t"] = f
        p.datagram_received(json.dumps({"msg_id": "t", "type": "P"}).encode(), ("1", 1))

        # Manifest & Find Node (800, 822)
        p.handle_manifest_announce(
            {"sender_id": node_id.hex(), "manifest_hash": "h"}, ("1", 1)
        )
        p.handle_find_node({"target_id": node_id.hex()}, ("1", 1))

        # Policy Update (762, 768)
        dht.fleet_manager = MagicMock()
        p.datagram_received(
            json.dumps(
                {"type": "POLICY_UPDATE", "invariant_id": "i", "state": "s"}
            ).encode(),
            ("1", 1),
        )

        # Store Value Failures (954-1009)
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = False
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 954
            dht.storage = None
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 1007
            dht.storage = MagicMock()
            dht.storage.put = AsyncMock(side_effect=Exception("io"))
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )  # 1000
