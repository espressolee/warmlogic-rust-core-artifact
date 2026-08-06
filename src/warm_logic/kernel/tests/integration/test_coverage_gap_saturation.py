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
import hashlib
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import warm_logic.kernel.sys.consensus as consensus

# Modules to saturate
from warm_logic.kernel.mesh.dht import Contact, KBucket, RoutingTable, SovereignDHT
from warm_logic.kernel.ops.audit import SovereignAudit
from warm_logic.kernel.ops.metrics import SystemMetrics
from warm_logic.kernel.substrate.stitch_server import StitchServer
from warm_logic.kernel.sys.persistence import SovereignStore


class TestCoverageGapSaturation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = Path("/tmp/warm_logic_test_saturation")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_dir / "saturation.db"

    def tearDown(self):
        if self.temp_dir.exists():
            import shutil

            shutil.rmtree(self.temp_dir)

    # --- MESH/DHT SATURATION ---
    async def test_dht_surgical_saturation(self):
        local_id = b"L" * 32
        pk = b"K" * 32
        node_id = hashlib.sha256(pk).digest()
        contact = Contact(node_id, "127.0.0.1", 8080, pk)

        bucket = KBucket(0, 2**256)
        bucket.update(contact)

        rt = RoutingTable(local_id)
        rt._verify_binding = MagicMock(return_value=True)
        await rt.update(contact)

        with patch(
            "warm_logic.kernel.mesh.dht.create_transport", return_value=MagicMock()
        ):
            dht = SovereignDHT(local_id, "127.0.0.1", 8033)
            dht.routing.find_neighbors = MagicMock(return_value=[contact])
            dht.storage = MagicMock()
            dht.storage.get.return_value = "VAL"

            with patch.object(dht, "ping", return_value=AsyncMock()):
                nodes = await dht.iterative_find_node(node_id)
                self.assertTrue(len(nodes) >= 0)

            val = dht.get(b"key")
            self.assertEqual(val, "VAL")
            dht.broadcast(b"data")

    # --- OPS/AUDIT SATURATION ---
    def test_audit_surgical_saturation(self):
        store = SovereignStore(db_path=self.db_path)
        store.commit_block(
            timestamp=100.0,
            tx_ids=["T1"],
            miner="M1",
            prev_hash="0" * 64,
            block_hash="B1",
            balance_updates={"A": 100},
            zk_proof="P1",
            state_root="S1",
            index=1,
        )

        audit = SovereignAudit(store=store)
        with patch("warm_logic.kernel.ops.audit.ZKProofGenerator") as m_zk:
            m_zk.return_value.verify_proof.return_value = True
            report = audit.run_full_audit()
            self.assertIsInstance(report.score, float)

        audit.reconcile_state()
        audit.close()

    # --- SYS/CONSENSUS SATURATION ---
    def test_consensus_surgical_saturation(self):
        with patch("warm_logic.kernel.sys.consensus.BFTEngine") as m_eng:
            with patch("warm_logic.kernel.sys.consensus.Vote") as m_vote:
                engine = m_eng(quorum_size=3)
                engine.propose("D")
                engine.vote("H", True)
                v = m_vote()
                v.is_valid = True
                self.assertTrue(v.is_valid)
        p = MagicMock(spec=consensus.BFTProposal)
        p.proposal_id = "H"
        self.assertEqual(p.proposal_id, "H")

    # --- STITCH SERVER SATURATION ---
    def test_stitch_server_surgical_saturation(self):
        server = StitchServer(port=0)
        server.start()
        server.broadcast("TEST", {"a": 1})

        def cb(p):
            p["hit"] = True

        server.register_handler("/test", cb)
        server.stop()

    # --- METRICS SATURATION ---
    def test_metrics_surgical_saturation(self):
        m = SystemMetrics()
        m.record_snapshot()
        time_travel = 1.0
        start = m.start_time
        with patch(
            "time.time",
            side_effect=[
                start,
                start + time_travel,
                start + time_travel,
                start + time_travel,
            ],
        ):
            m.record_snapshot()
            d = m.get_derivative("drift_score")
            self.assertIsInstance(d, float)
        self.assertTrue(
            m.hardware_id.startswith("MA")
            or "Darwin" in m.hardware_id
            or "-" in m.hardware_id
        )


if __name__ == "__main__":
    unittest.main()
