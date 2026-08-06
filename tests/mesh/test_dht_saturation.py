import asyncio
import base64
import hashlib
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.kernel.mesh.dht import (
    ALPHA,
    K_PARAM,
    Contact,
    DHTProtocol,
    KBucket,
    RoutingTable,
    SovereignDHT,
)
from warm_logic.kernel.mesh.transport import AbstractTransport


# Global patch to disable Rust for Python logic saturation
@pytest.fixture(autouse=True)
def disable_rust():
    with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
        yield


class TestDHTSaturation:
    @pytest.fixture
    def node_id(self):
        return os.urandom(32)

    def create_contact(self, name: str, port: int = 10000):
        pk = name.encode().ljust(32, b"\x00")
        nid = hashlib.sha3_256(pk).digest()
        return Contact(
            node_id=nid,
            address="127.0.0.1",
            port=port,
            public_key=pk,
            silicon_id="HW_" + name,
            capabilities={"CPU": 1},
        )

    def init_dht_clean(self, node_id):
        dht = SovereignDHT(
            node_id=node_id,
            address="127.0.0.1",
            port=12345,
            public_key=b"pubkey_fixed",
            private_key="privkey_fixed",
        )
        dht.silicon_id = "HW_DEVICE_0"
        dht.capabilities = {"ROLE": 1}
        dht.storage = {}
        return dht

    # --- Basic Coverage ---
    def test_basic_methods(self, node_id):
        dht = self.init_dht_clean(node_id)
        dht.store(b"k", "v")
        assert dht.get(b"k") == "v"
        assert len(dht.find_node(b"target")) == 0
        assert dht.server is None

    def test_contact_comparison(self):
        c1 = self.create_contact("A")
        c2 = self.create_contact("B")
        assert c1.xor_distance(c2.node_id) > 0

    # --- RoutingTable Coverage ---
    @pytest.mark.asyncio
    async def test_rt_saturation_refined(self):
        rt = RoutingTable(b"\x00" * 32)
        # 1. PQC Gate fail
        c_bad = Contact(
            b"BAD" * 10 + b"XX", "1.1.1.1", 80, public_key=b"P" * 32, silicon_id="S"
        )
        await rt.update(c_bad)

        # 2. Split (Using low ID local to force split on lower half)
        with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
            c1 = self.create_contact("C1")
            await rt.update(c1)
            c2 = self.create_contact("C2")
            await rt.update(c2)
            assert len(rt.buckets) > 1

        # 3. Eviction (Use high ID local so c1/c2 land in a bucket that doesn't split)
        rt_evict = RoutingTable(b"\xff" * 32)
        with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
            c1 = self.create_contact("C1")
            await rt_evict.update(c1)

            # First split to move c1 to bucket[0] and local to bucket[1]
            c_high = Contact(
                b"\xf0" + b"\x00" * 31,
                "1.1.1.3",
                100,
                public_key=b"P" * 32,
                silicon_id="S",
            )
            # Wait, even easier: just add c1, and then add c2.
            # Local is \xff..., c1 is \x2b...
            # First add c1 -> [0, 2**256] has c1.
            # Then add c2 -> bucket is full, local is in bucket, split.
            # After split: bucket 0 [0, 2**255] has c1. bucket 1 [2**255+1, 2**256] has local ID.
            # Then re-update c2. c2 (\xcd...) goes to bucket 1.
            # Wait, 0xcd is > 127, so it goes to bucket 1!
            # Let's use name "A" -> starts with 0x2b? No, 'A' is 0x41.
            # 'C1' is 0x43. 'C2' is 0x43.
            # sha3_256(b'C1'...) starts with 0x2b.
            # sha3_256(b'C2'...) starts with 0xcd.
            # So c1 is in bucket 0, c2 is in bucket 1.

            # To test EVICTION, we need to add a second contact to bucket 0 that is NOT local.
            c_other = self.create_contact(
                "Other"
            )  # sha3_256(b'Other'...) -> starts with 0xbd? No.
            # Let's just create contacts until we hit one in bucket 0.

            dht_mock = MagicMock()
            dht_mock.ping = AsyncMock(return_value=False)

            # Manually fill a bucket and force eviction
            rt_evict = RoutingTable(b"\xff" * 32)
            rt_evict.buckets[0].contacts = [c1]
            with patch("warm_logic.kernel.mesh.dht.K_PARAM", 1):
                # c1 is in bucket 0, local (\xff) is NOT in bucket 0.
                await rt_evict.update(c1)  # Still c1
                # Add c2 which also lands in bucket 0 (if we are lucky)
                # Actually, I'll just MOCK find_neighbors to return bucket 0.
                with patch.object(rt_evict, "buckets", [KBucket(0, 2**256)]):
                    rt_evict.buckets[0].contacts = [c1]
                    # Forced full bucket without local ID
                    await rt_evict.update(c2, dht=dht_mock)
                    assert rt_evict.buckets[0].contacts[0].node_id == c2.node_id

    # --- SovereignDHT Coverage ---
    @pytest.mark.asyncio
    async def test_dht_lifecycle_refined(self, node_id):
        dht = self.init_dht_clean(node_id)
        with patch(
            "warm_logic.kernel.mesh.dht.discover_public_address",
            return_value=("1.1.1.1", 99),
        ):
            with patch("warm_logic.kernel.mesh.dht.create_transport") as mt:
                trans = MagicMock(spec=AbstractTransport)
                trans.start_server = AsyncMock()
                trans.close = MagicMock()
                mt.return_value = trans
                await dht.start(enable_nat_discovery=True)
                dht.announce_presence()
                await dht.stop()

    @pytest.mark.asyncio
    async def test_bootstrap_logic(self, node_id, tmp_path):
        dht = self.init_dht_clean(node_id)
        dht.transport = MagicMock()
        dht.transport.close = MagicMock()

        with patch("os.getcwd", return_value=str(tmp_path)):
            # Load fleet.json
            cpath = tmp_path / "configs"
            cpath.mkdir()
            (cpath / "fleet.json").write_text(
                json.dumps({"trust_anchors": [{"address": "10.0.0.1", "port": 9000}]})
            )
            with patch.object(dht, "iterative_find_node", new_callable=AsyncMock):
                await dht.bootstrap()
                assert dht.transport.sendto.called

    @pytest.mark.asyncio
    async def test_iterative_find_node_full(self, node_id):
        dht = self.init_dht_clean(node_id)
        dht.transport = MagicMock()
        c1 = self.create_contact("S1")
        dht.routing.buckets[0].contacts.append(c1)

        async def mock_rpc(*args, **kwargs):
            return {
                "type": "NODES",
                "nodes": [{"id": os.urandom(32).hex(), "addr": "2.2.2.2", "port": 88}],
            }

        with patch.object(dht, "rpc_call", side_effect=mock_rpc):
            await dht.iterative_find_node(os.urandom(32))

    # --- Protocol Coverage ---
    @pytest.mark.asyncio
    async def test_protocol_handlers_exhaustive(self, node_id):
        dht = self.init_dht_clean(node_id)
        dht.transport = MagicMock()
        dht.transport.close = MagicMock()
        proto = DHTProtocol(dht)
        proto.transport = dht.transport
        dht._protocol = proto

        addr = ("1.1.1.1", 100)

        def send(m):
            m["sender_id"] = os.urandom(32).hex()
            proto.datagram_received(json.dumps(m).encode(), addr)

        # Diverse messages
        send({"type": "PING", "msg_id": "r1"})
        send({"type": "FIND_NODE", "target_id": os.urandom(32).hex(), "msg_id": "r2"})
        send({"type": "MANIFEST_ANNOUNCE", "manifest_hash": "h1"})

        # Registration & Mutation
        dht.service_registry = MagicMock()
        send({"type": "SERVICE_REGISTRATION_PROPOSAL"})
        send(
            {
                "type": "SERVICE_REGISTRATION_VOTE",
                "voter_id": "v1",
                "proposal_id": "p1",
                "vote": True,
            }
        )

        dht.gossip_agent = MagicMock()
        send({"type": "MUTATION_PROPOSAL", "mutation_id": "m1"})
        send({"type": "MUTATION_VOTE", "mutation_id": "m1", "vote": True})

        # Anti-entropy
        dht.anti_entropy_agent = MagicMock()
        dht.anti_entropy_agent._merkle.get_subtree_hashes.return_value = ["h1"]
        dht.anti_entropy_agent._get_local_state.return_value = {"k": "v"}
        send({"type": "MERKLE_ROOT_REQUEST"})
        send({"type": "SUBTREE_HASHES_REQUEST"})
        send({"type": "SUBTREE_RECORDS_REQUEST", "subtree_idx": 0})

        # Policy & Revoke
        dht.fleet_manager = MagicMock()
        send({"type": "POLICY_UPDATE", "invariant_id": "i1", "state": "s1"})
        send(
            {
                "type": "REVOKE_NODE",
                "revoke_id": os.urandom(32).hex(),
                "signature": "MASTER_VETO",
            }
        )

        # Store Value
        dht.storage = {}
        with patch("warm_logic_rs.RustZKProofGenerator") as zk:
            zk.return_value.verify_state_proof.return_value = True
            send(
                {
                    "type": "STORE_VALUE",
                    "key": "k",
                    "value": "v",
                    "zk_proof": "p",
                    "commitment": "c",
                }
            )

        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_dht_edge_cases_final(self, node_id):
        dht = self.init_dht_clean(node_id)
        dht.transport = MagicMock()
        dht.transport.close = MagicMock()

        # Broadcast/Ping failures
        dht.transport.sendto.side_effect = Exception("crash")
        dht.broadcast_network(b"msg")
        dht.broadcast(b"data")
        assert await dht.ping(self.create_contact("P1")) is False

        # Storage exceptions
        dht.storage = MagicMock()
        dht.storage.close.side_effect = Exception("fail")
        await dht.stop()
