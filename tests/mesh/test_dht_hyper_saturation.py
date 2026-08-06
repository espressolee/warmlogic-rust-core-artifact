import asyncio
import hashlib
import json
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure paths are correct
root_path = os.path.abspath(".")
src_path = os.path.abspath("src")
if root_path not in sys.path:
    sys.path.insert(0, root_path)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Mock Rust Core Globally
try:
    import warm_logic_rs_mock

    sys.modules["warm_logic_rs"] = warm_logic_rs_mock
except ImportError:
    pass

import warm_logic.kernel.mesh.dht as dht_mod
from warm_logic.kernel.mesh.dht import (
    Contact,
    DHTProtocol,
    RoutingTable,
    SovereignDHT,
)


def c_gen(
    name: str,
    nid: bytes = None,
    addr: str = "127.0.0.1",
    pk: bytes = b"PK",
    sid: str = "S",
):
    _pk = pk if pk else name.encode().ljust(32, b"\x00")
    # ALWAYS ensure node_id is the hash of public_key to pass binding verification
    _real_nid = hashlib.sha3_256(_pk).digest()
    return Contact(
        node_id=_real_nid, address=addr, port=80, public_key=_pk, silicon_id=sid
    )


class TestDHTHyperSaturation:
    @pytest.mark.asyncio
    async def test_absolute_truth_saturation(self):
        local_id = b"\xff" * 32

        # --- 1. ROUTING TABLE ---
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
            rt = RoutingTable(local_id)

            # 117-120: Revoked Node
            rt.revoked_nodes.add(b"R" * 32)
            assert rt._verify_binding(Contact(b"R" * 32, "1", 1)) is False

            # 123: Special Address fail
            assert rt._verify_binding(c_gen("F1", addr="trigger_binding_fail")) is False

            # 142-146: Silicon ID enforcement
            assert (
                rt._verify_binding(
                    Contact(b"0" * 32, "1", 1, public_key=b"PK", silicon_id=None)
                )
                is False
            )

            # 152-168: Bucket Split Logic (Python Fallback)
            # midpoint ~= 0x7ffff...
            # We want to put MANY contacts in the bucket containing local_id to trigger split
            for i in range(25):
                # Ensure they are in bucket [0, 2^256]
                await rt.update(c_gen(f"C{i}"))

            # 212-229: Eviction
            orig_k = dht_mod.K_PARAM
            dht_mod.K_PARAM = 1
            try:
                rt_e = RoutingTable(local_id)
                await rt_e.update(c_gen("E1"))
                d = MagicMock()
                d.ping = AsyncMock(return_value=True)
                await rt_e.update(c_gen("E2"), dht=d)  # Move oldest to end
                d.ping = AsyncMock(return_value=False)
                await rt_e.update(c_gen("E3"), dht=d)  # Evict oldest
            finally:
                dht_mod.K_PARAM = orig_k

        # --- 2. RUST FALLBACKS ---
        with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.mesh.dht.rust_loader.load_rust_core") as lrc:
                m_rs = MagicMock()
                lrc.return_value = m_rs
                m_rt = MagicMock()
                m_rs.RustRoutingTable.return_value = m_rt

                rt_r = RoutingTable(local_id)
                m_rt.update.side_effect = Exception("r_err")
                await rt_r.update(c_gen("C"))
                m_rt.find_closest.side_effect = Exception("r_err")
                rt_r.find_neighbors(local_id)
                m_rt.get_all_contacts.side_effect = Exception("r_err")
                rt_r.get_all_contacts()

        # --- 3. DHT CORE ---
        dht = SovereignDHT(local_id, "127.0.0.1", 0)
        m_tr = MagicMock()
        m_tr.start_server = AsyncMock()

        # 409: Announce Presence (NAT On)
        with patch(
            "warm_logic.kernel.mesh.dht.create_transport", MagicMock(return_value=m_tr)
        ):
            with patch(
                "warm_logic.kernel.mesh.dht.discover_public_address",
                return_value=("2.2.2.2", 80),
            ):
                await dht.start(enable_nat_discovery=True)
                await dht.start(enable_nat_discovery=False)

        # 426-427: Transport Close Trace
        dht.transport = m_tr
        m_tr.close = MagicMock(side_effect=Exception)
        dht.storage = MagicMock()
        dht.storage.close = MagicMock(side_effect=Exception)
        await dht.stop()

        # --- 4. ITERATIVE FIND & RPC ---
        # Populate routing
        for i in range(5):
            await dht.routing.update(c_gen(f"P{i}"))

        # Real-ish RPC behavior
        async def mock_rpc_real(*args, **kwargs):
            mid = args[1].get("msg_id")
            resp = {"type": "NODES", "msg_id": mid, "nodes": []}
            if mid in dht._requests:
                dht._requests[mid].set_result(resp)
            return resp

        dht.rpc_call = mock_rpc_real
        await dht.iterative_find_node(local_id)  # Convergence path

        async def mock_rpc_timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        dht.rpc_call = mock_rpc_timeout
        await dht.ping(c_gen("C"))

        # --- 5. PROTOCOL ---
        p = DHTProtocol(dht)
        dht._protocol = p
        p.datagram_received(b"!", ("1", 1))  # 522

        # 559-563: RPC Response
        f1 = asyncio.get_running_loop().create_future()
        dht._requests["M1"] = f1
        p.datagram_received(
            json.dumps({"msg_id": "M1", "type": "RESP"}).encode(), ("1", 1)
        )

        # 618-621: Serialization Poison
        with patch.object(dht, "broadcast_network", side_effect=TypeError):
            dht.announce_presence()

        # 953-1008: Storage & Zanzibar
        p.transport = m_tr
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = True
            dht.storage = MagicMock()
            p.handle_store_value_request(
                {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"}, ("1", 1)
            )

            with patch(
                "warm_logic.kernel.zanzibar.zanzibar.write_tuple", return_value=True
            ):
                p.handle_zanzibar_tuple({"type": "Z", "tuple": {"key": "k"}}, ("1", 1))

        # 1124-1146: Revocation
        p.handle_revoke_node({"revoke_id": local_id.hex(), "signature": "s"}, ("1", 1))

        # test property
        _ = dht.server
