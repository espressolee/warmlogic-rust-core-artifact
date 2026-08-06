# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import asyncio
from contextlib import nullcontext
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from warm_logic.kernel.sys.consensus import BFTEngine, Vote
from warm_logic.kernel.sys.cryptography import MLDSA
from warm_logic.kernel.sys.network import MeshNetworking
from warm_logic.kernel.sys.persistence import SovereignStore


class TestSystemCluster(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    async def test_sovereign_store(self):
        db_path = Path(self.tmp_dir) / "test.db"
        # Bypassing Rust mode for this unit test to verify forensic SQLite logic
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(db_path)

        try:
            # 1. Event Log
            store.log_event(
                100.0, "TEST", {"key": "val"}, "prev", "curr", "root", "proof"
            )
            self.assertEqual(store.get_last_event()["hash"], "curr")
            all_ev = store.get_all_events()
            self.assertEqual(len(all_ev), 1)
            self.assertEqual(all_ev[0]["event_type"], "TEST")

            # 2. Metadata
            store.set_meta("config", {"a": 1})
            self.assertEqual(store.get_meta("config")["a"], 1)
            self.assertIsNone(store.get_meta("missing"))

            # 3. Blocks & Balances
            store.commit_block(
                200.0, ["tx1"], "miner1", "curr", "block1", {"addr1": 50}, "zkp"
            )
            self.assertEqual(store.get_balance("addr1"), 50)
            self.assertEqual(store.get_all_balances(), {"addr1": 50})
            self.assertEqual(store.get_last_block()["hash"], "block1")

            store.commit_block(
                300.0, ["tx2"], "miner2", "block1", "block2", {"addr1": 40}
            )
            self.assertEqual(store.get_balance("addr1"), 40)
        finally:
            store.close()

    def test_store_default_path(self):
        # Coverage for __init__ default path logic
        # Disable Rust store to isolate SQLite default path behavior
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            with patch("pathlib.Path.mkdir"):
                with patch("sqlite3.connect"):
                    s = SovereignStore(None)
                    self.assertTrue(str(s.db_path).endswith("sovereign.db"))

    async def test_mesh_networking(self):
        from warm_logic.kernel import rust_loader

        class _FakePQCKeypair:
            @staticmethod
            def generate():
                return ("SIM_PQC_PK", "SIM_PQC_SK")

        class _FakeSovereignStore(dict):
            def put(self, key, value):
                self[key] = value

            def get(self, key):
                return super().get(key)

            def close(self):
                return None

        fake_rs = SimpleNamespace(
            PQCKeypair=_FakePQCKeypair,
            SovereignStore=lambda *_args, **_kwargs: _FakeSovereignStore(),
        )
        rust_context = (
            nullcontext()
            if rust_loader.HAS_RUST_CORE
            else patch.multiple(
                rust_loader,
                HAS_RUST_CORE=True,
                load_rust_core=lambda: fake_rs,
            )
        )

        with rust_context:
            # 1. Init with ID generation
            with patch("warm_logic.kernel.sys.network.SovereignDHT"):
                mn = MeshNetworking()
                self.assertIsNotNone(mn.dht)

            # 2. Ignite/Connect/Stats
            mn = MeshNetworking(b"id", "127.0.0.1", 0)
            mn.dht.start = MagicMock(return_value=asyncio.Future())
            mn.dht.start.return_value.set_result(None)
            mn.dht.bootstrap = MagicMock(return_value=asyncio.Future())
            mn.dht.bootstrap.return_value.set_result(None)

            await mn.ignite([("seed", 1)])

            from warm_logic.kernel.mesh.dht import Contact

            mn.dht.routing = MagicMock()
            mn.dht.routing.find_neighbors.return_value = [
                Contact(b"p1", "1.2.3.4", 4000, public_key=b"pk1"),
                Contact(b"p2", "1.2.3.5", 4001, public_key=b"pk2"),
            ]
            self.assertEqual(mn.broadcast(b"msg"), 2)

            st = mn.get_mesh_status()
            self.assertEqual(st["peer_count"], 2)
            self.assertTrue(st["pqc_bound"])

    def test_bft_engine(self):
        engine = BFTEngine(3)  # Quorum = 3

        # Initialize round state (Required by Rust BFTEngine)
        engine.start_round(1)
        engine.propose("h1")

        # We need real signatures because Rust BFTEngine verifies them internally
        mldsa = MLDSA()
        kp1 = mldsa.generate_keypair()
        kp2 = mldsa.generate_keypair()
        kp3 = mldsa.generate_keypair()

        def make_vote(block_hash, kp, decision):
            # intent = f"VOTE:{block_hash}:{decision}" # OLD
            intent = block_hash  # NEW Hypothesis
            sig = mldsa.sign(intent, kp.private_key)
            return Vote(block_hash, kp.public_key, sig)

        v1 = make_vote("h1", kp1, "APPROVE")
        v2 = make_vote("h1", kp2, "APPROVE")
        v3 = make_vote("h1", kp3, "APPROVE")

        self.assertFalse(engine.cast_vote(v1))
        self.assertFalse(engine.cast_vote(v2))
        self.assertTrue(engine.cast_vote(v3))  # Commit

        # Rejection (Actually, if decision is implicit, voting IS approving?)
        # If we want to REJECT, we just don't vote? Or vote for something else?
        # Rust Vote struct has no decision field.
        # So casting a vote implies supporting the hash.

        # Testing Bad Sig
        v_bad = Vote("h3", kp1.public_key, "bad_sig")
        self.assertFalse(engine.cast_vote(v_bad))
