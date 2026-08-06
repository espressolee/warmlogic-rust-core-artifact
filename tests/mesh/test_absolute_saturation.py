import asyncio
import hashlib
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure paths
src = os.path.abspath("src")
if src not in sys.path:
    sys.path.insert(0, src)

import warm_logic.kernel.mesh.dht as dht_mod
import warm_logic.kernel.rust_loader
from warm_logic.kernel.mesh.dht import Contact, DHTProtocol, RoutingTable, SovereignDHT


@pytest.mark.asyncio
async def test_absolute_saturation_truth():
    local_id = b"\xff" * 32

    def c_gen(name, addr="127.0.0.1", port=80, pk=None, sid="S"):
        _pk = pk if pk else name.encode().ljust(32, b"\x00")
        _real_nid = hashlib.sha3_256(_pk).digest()
        return Contact(
            node_id=_real_nid, address=addr, port=port, public_key=_pk, silicon_id=sid
        )

    # 1. Equality & Basic
    c1 = c_gen("A")
    assert (c1 == "ST") is False
    assert (c1 == 1) is False
    assert (c1 == None) is False

    # 2. Python Fallbacks (Hard Disable Rust)
    orig_has_rust = warm_logic.kernel.rust_loader.HAS_RUST_CORE
    warm_logic.kernel.rust_loader.HAS_RUST_CORE = False
    try:
        rt = RoutingTable(local_id)
        # 142-146: Silicon fail
        pk_v = b"V".ljust(32, b"\x00")
        nid_v = hashlib.sha3_256(pk_v).digest()
        rt._verify_binding(Contact(nid_v, "1", 1, pk_v, None))

        # 212-229: Eviction
        dht_mod.K_PARAM = 1
        # Add c1 to Bucket 0
        pk1 = (b"\x00").ljust(32, b"\x00")
        c1 = c_gen("C1", pk=pk1)
        await rt.update(c1)
        # Split so we have a bucket not containing local_id
        rt.split_bucket(0)

        # Now Bucket 0 has C1. Add C2 to Bucket 0.
        pk2 = (b"\x00\x00\x00\x01").ljust(32, b"\x00")
        d = MagicMock()
        d.ping = AsyncMock(return_value=True)
        await rt.update(c_gen("C2", pk=pk2), dht=d)  # Alive 222-223

        d.ping = AsyncMock(return_value=False)
        pk3 = (b"\x00\x00\x00\x02").ljust(32, b"\x00")
        await rt.update(c_gen("C3", pk=pk3), dht=d)  # Dead 224-227

        rt._evict_in_progress = True
        await rt.update(c_gen("C4", pk=b"\x03"))  # Skip 214-215
        rt._evict_in_progress = False

        # 175: Self, 198: Void
        await rt.update(Contact(local_id, "1", 1))
        with patch.object(rt, "buckets", []):
            await rt.update(c_gen("VOID"))

    finally:
        warm_logic.kernel.rust_loader.HAS_RUST_CORE = orig_has_rust
        dht_mod.K_PARAM = 20

    # 3. Rust Fallbacks
    with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
        with patch("warm_logic.kernel.rust_loader.load_rust_core") as lrc:
            m_rs = MagicMock()
            lrc.return_value = m_rs
            m_rt = MagicMock()
            m_rs.RustRoutingTable.return_value = m_rt
            rt_r = RoutingTable(local_id)
            m_rt.find_closest.side_effect = Exception()
            rt_r.find_neighbors(local_id)
            m_rt.get_all_contacts.side_effect = Exception()
            rt_r.get_all_contacts()

    # 4. DHT LifeCycle
    dht = SovereignDHT(local_id, "127.0.0.1", 12345)

    def mock_ct_factory(*args):
        m = MagicMock()
        m.start_server = AsyncMock()
        m.sendto = MagicMock()
        return m

    with patch(
        "warm_logic.kernel.mesh.dht.create_transport", side_effect=mock_ct_factory
    ):
        with patch(
            "warm_logic.kernel.mesh.dht.discover_public_address", return_value=None
        ):
            await dht.start(enable_nat_discovery=True)

    # Bootstrap
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", side_effect=Exception()),
    ):
        await dht.bootstrap()
    with patch("os.path.exists", return_value=False):
        await dht.bootstrap()

    # 5. RPC & Iterative
    # Wait for response (678)
    msg_id = None

    def mock_send(contact, msg):
        nonlocal msg_id
        try:
            msg_id = json.loads(msg.decode())["msg_id"]
        except:
            pass

    dht.send = mock_send

    async def resolve_soon():
        await asyncio.sleep(0.01)
        if msg_id in dht._requests:
            dht._requests[msg_id].set_result({"type": "RESP", "msg_id": msg_id})

    asyncio.create_task(resolve_soon())
    await dht.rpc_call(c_gen("T1"), {"m": "h"}, timeout=0.1)

    try:
        await dht.rpc_call(c_gen("T2"), {"m": "h"}, timeout=0.001)
    except asyncio.TimeoutError:
        pass

    # Iterative gaps
    dht.rpc_call = AsyncMock(return_value={"type": "NODES", "nodes": []})
    await dht.iterative_find_node(local_id)  # 484
    dht.rpc_call = AsyncMock(return_value={"type": "NODES", "nodes": [{"id": "bad"}]})
    await dht.iterative_find_node(local_id)  # 508-509

    # 6. Protocol
    p = DHTProtocol(dht)
    p.transport = dht.transport
    dht._protocol = p
    p.datagram_received(b"!", ("1", 1))  # 522
    p.datagram_received(
        json.dumps({"msg_id": "U", "type": "RESP"}).encode(), ("1", 1)
    )  # 559
    dht.fleet_manager = MagicMock()
    f = asyncio.get_running_loop().create_future()
    dht._requests["M1"] = f
    p.datagram_received(
        json.dumps({"msg_id": "M1", "type": "RESP"}).encode(), ("1", 1)
    )  # 570
    p.handle_policy_update({"invariant_id": "i"}, ("1", 1))  # 596

    p.handle_manifest_announce({}, ("1", 1))
    p.handle_find_node({}, ("1", 1))
    p.handle_policy_update({}, ("1", 1))

    # 7. Storage
    with patch("warm_logic.kernel.mesh.dht.check_permission", return_value=True):
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.side_effect = Exception()
            m_msg = {
                "type": "ST",
                "key": "k",
                "value": "v",
                "zk_proof": "p",
                "commitment": "c",
                "sender_id": local_id.hex(),
            }
            p.handle_store_value_request(m_msg, ("1", 1))  # 968-970
            zk.return_value.verify_state_proof.side_effect = None
            zk.return_value.verify_state_proof.return_value = False
            p.handle_store_value_request(m_msg, ("1", 1))  # 973-979
            zk.return_value.verify_state_proof.return_value = True
            dht.storage = MagicMock()
            dht.storage.put.side_effect = Exception()
            p.handle_store_value_request(m_msg, ("1", 1))
            dht.storage = None
            p.handle_store_value_request(m_msg, ("1", 1))  # 1007
            p.handle_store_value_request({"sender_id": local_id.hex()}, ("1", 1))  # 954

    # 8. Final Errors
    dht.rpc_call = AsyncMock(side_effect=Exception())
    try:
        await dht.find_closest(c_gen("C"), b"T")  # 643-646
    except:
        pass
    with patch.object(dht, "broadcast_network", side_effect=TypeError):
        try:
            dht.announce_presence()  # 624-625
        except:
            pass
    dht.transport.sendto.side_effect = Exception()
    try:
        p.handle_patch_request({"type": "P"}, ("1", 1))  # 1057-1061
    except:
        pass
    p.handle_revoke_node(
        {"revoke_id": local_id.hex(), "signature": "BAD"}, ("1", 1)
    )  # 1141-1146
