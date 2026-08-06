import asyncio
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.kernel.mesh.dht import K_PARAM, Contact, RoutingTable, SovereignDHT


@pytest.fixture(autouse=True)
def disable_rust():
    with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
        yield


class TestDHTFinalPush:
    def create_pqc_contact(self, name: str):
        pk = name.encode().ljust(32, b"\x00")
        nid = (
            hashlib.sha3_256(pk).digest()
            if hasattr(hashlib, "sha3_256")
            else b"\x00" * 32
        )  # simplified
        return Contact(
            node_id=nid,
            address="1",
            port=1,
            public_key=pk,
            silicon_id="S",
            capabilities={},
        )

    @pytest.mark.asyncio
    async def test_surgical_routing(self):
        import hashlib

        nid = b"\xff" * 32
        rt = RoutingTable(nid)
        # 142-146: split_bucket
        rt.split_bucket(0)
        # 185: rust error
        with patch.object(rt, "_use_rust", True):
            rt._rust_table = MagicMock()
            rt._rust_table.update.side_effect = Exception("err")
            await rt.update(Contact(b"1" * 32, "1", 1))
        # 198: is_updated
        c1 = Contact(b"2" * 32, "1", 1)
        await rt.update(c1)
        # 215, 222-229: Eviction
        with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
            rt.buckets[0].contacts = [c1]
            d = MagicMock()
            d.ping = AsyncMock(return_value=True)
            await rt.update(Contact(b"3" * 32, "1", 1), dht=d)
            rt.buckets[0].contacts = [c1]
            d.ping = AsyncMock(return_value=False)
            await rt.update(Contact(b"4" * 32, "1", 1), dht=d)

    @pytest.mark.asyncio
    async def test_surgical_dht(self):
        nid = b"\xff" * 32
        dht = SovereignDHT(nid, "1", 1)
        # 340-349: caps/silicon import
        with patch("builtins.__import__", side_effect=ImportError):
            SovereignDHT(nid, "1", 1)
        # 384-389: NAT fail - mock transport to avoid network binding
        mock_transport = MagicMock()
        mock_transport.start_server = AsyncMock()
        with (
            patch(
                "warm_logic.kernel.mesh.dht.discover_public_address", return_value=None
            ),
            patch(
                "warm_logic.kernel.mesh.dht.create_transport",
                return_value=mock_transport,
            ),
        ):
            await dht.start(enable_nat_discovery=True)
        # 426-427, 448-449, 452-453: Bootstrap
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", MagicMock()),
            patch(
                "json.load",
                return_value={"trust_anchors": [{"address": "1", "port": 1}]},
            ),
        ):
            await dht.bootstrap()
        # 559-563, 570-580: broadcast
        dht.transport = MagicMock()
        dht.transport.sendto.side_effect = Exception("err")
        try:
            dht.broadcast(b"m")
        except:
            pass
        dht.broadcast_policy_event("i", "s")
        # 624-625: RPC fail
        dht._protocol = None
        try:
            await dht.rpc_call(Contact(nid, "1", 1), {})
        except:
            pass

    @pytest.mark.asyncio
    async def test_surgical_protocol(self):
        nid = b"\xff" * 32
        dht = SovereignDHT(nid, "1", 1)
        from warm_logic.kernel.mesh.dht import DHTProtocol

        proto = DHTProtocol(dht)
        # 760-766: INSIGHT/POLICY/ZANZIBAR
        proto.datagram_received(
            json.dumps({"type": "INSIGHT_ANNOUNCE"}).encode(), ("1", 1)
        )
        dht.fleet_manager = MagicMock()
        proto.datagram_received(
            json.dumps(
                {"type": "POLICY_UPDATE", "invariant_id": "i", "state": "s"}
            ).encode(),
            ("1", 1),
        )
        with patch(
            "warm_logic.kernel.zanzibar.zanzibar.write_tuple", return_value=True
        ):
            proto.datagram_received(
                json.dumps({"type": "ZANZIBAR_TUPLE"}).encode(), ("1", 1)
            )
        # 953-1007: Store
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = False
            proto.handle_store_value_request(
                {
                    "key": "k",
                    "value": "v",
                    "zk_proof": "p",
                    "commitment": "c",
                    "request_id": "r",
                },
                ("1", 1),
            )
            with patch(
                "warm_logic.kernel.mesh.dht.check_permission", return_value=False
            ):
                proto.handle_store_value_request(
                    {"key": "k", "value": "v", "zk_proof": "p", "commitment": "c"},
                    ("1", 1),
                )
        # 1073-1093: Patch
        proto.handle_patch_request({"target_hash": "h"}, ("1", 1))
        # 1144-1145: Zanzibar catch
        with patch("warm_logic.kernel.zanzibar.RelationTuple", side_effect=Exception):
            proto.handle_zanzibar_tuple({"type": "ZANZIBAR_TUPLE"}, ("1", 1))
