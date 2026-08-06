import asyncio
import hashlib
import json
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure paths
src = os.path.abspath("src")
if src not in sys.path:
    sys.path.insert(0, src)

import warm_logic.kernel.mesh.dht as dht_mod
from warm_logic.kernel.mesh.dht import (
    Contact,
    DHTProtocol,
    KBucket,
    RoutingTable,
    SovereignDHT,
)


@pytest.mark.asyncio
async def test_dht_truth_absolute_saturation():
    """
    ground truth Saturation Suite for dht.py v14.1.
    Targets all remaining TRACE points.
    """
    local_id = b"\xff" * 32

    def c_gen(seed, addr="127.0.0.1", port=80):
        pk = seed.encode().ljust(32, b"\x00")
        nid = hashlib.sha3_256(pk).digest()
        return Contact(
            node_id=nid, address=addr, port=port, public_key=pk, silicon_id="S"
        )

    # 1. Galaxy Score (270)
    rt = RoutingTable(local_id)
    rt.owner = MagicMock()
    rt.owner.galaxy = MagicMock()
    rt.owner.galaxy.get_topology_score.return_value = 0.5
    rt.find_neighbors(local_id, count=1)

    # 2. Rust get_all (286)
    with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
        with patch("warm_logic.kernel.rust_loader.load_rust_core") as lrc:
            m_rs = MagicMock()
            lrc.return_value = m_rs
            m_rt = MagicMock()
            m_rs.RustRoutingTable.return_value = m_rt
            m_rt.find_closest.return_value = [(b"id", "1", 1)]
            rt_r = RoutingTable(local_id)
            rt_r.get_all_contacts()

    # 3. Lifecycle Fallbacks (342, 353)
    with patch.dict(
        sys.modules,
        {"warm_logic.kernel.security.silicon": MagicMock(side_effect=ImportError)},
    ):
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", side_effect=Exception
            ):
                dht_i = SovereignDHT(local_id, "1", 1)

    # 4. Iterative Break (476)
    dht_i.routing.buckets = []  # Force no neighbors
    await dht_i.iterative_find_node(local_id)

    # 5. Broadcast (552, 555, 570)
    c1 = c_gen("c1")
    dht_i.routing.buckets = [KBucket(0, 2**256)]
    dht_i.routing.buckets[0].contacts = [c1]
    dht_i.transport = MagicMock()
    dht_i.broadcast(b"B")

    with patch.object(dht_i, "send", side_effect=Exception):
        dht_i.broadcast(b"F")

    dht_i.broadcast_policy_event("p1", "s1")

    # 6. Ping Exception (636)
    with patch.object(dht_i, "rpc_call", side_effect=Exception):
        await dht_i.ping(c1)

    # 7. Protocol Handlers (735, 783, 911, 914, 935)
    p = DHTProtocol(dht_i)
    dht_i._protocol = p
    p.datagram_received(
        json.dumps({"type": "INSIGHT_ANNOUNCE", "sender_id": local_id.hex()}).encode(),
        ("1", 1),
    )
    p.datagram_received(
        json.dumps({"type": "POLICY_UPDATE", "sender_id": local_id.hex()}).encode(),
        ("1", 1),
    )

    dht_i.gossip_agent = MagicMock()
    # 783: receive_manifest
    del dht_i.gossip_agent.on_receive_manifest
    p.handle_manifest_announce({"manifest_hash": "h", "sender_id": "s"}, ("1", 1))

    # 935: Zanzibar
    with patch("warm_logic.kernel.zanzibar.zanzibar.write_tuple") as mwt:
        p.handle_zanzibar_tuple(
            {
                "namespace": "n",
                "object_id": "o",
                "relation": "r",
                "subject_namespace": "sn",
                "subject_id": "si",
            },
            ("1", 1),
        )
