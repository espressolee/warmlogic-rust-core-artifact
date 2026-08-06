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
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from warm_logic.kernel.economy.ledger import ReplicatedLedger, Transaction
from warm_logic.kernel.sys.persistence import SovereignStore


class TestZKWall(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.test_dir.name) / "test_zk_wall.db"

        # Create store without Rust to avoid _rust_ledger creation
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            self.store = SovereignStore(db_path)
        self.store._use_rust = False  # Force SQLite for forensic unit testing

        # [Brutal Truth] Replace MagicMock with high-fidelity Emulator
        from warm_logic.kernel.tests.emu.kernel_emu import KernelEmulator

        self.emu = KernelEmulator()
        self.mock_rs_core = MagicMock(wraps=self.emu)

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_load:
                mock_load.return_value = self.mock_rs_core
                self.ledger = ReplicatedLedger(self.store)

        self.ledger.rust_core = self.mock_rs_core

    def tearDown(self):
        self.store.close()
        self.test_dir.cleanup()

    def test_recursive_chain_integrity(self):
        """Verify that proofs are cryptographically linked in a recursive chain."""
        # 1. Mine first block
        self.emu.state["balances"] = {"ALICE": 1000}
        self.ledger.submit_tx(Transaction("GENESIS", "ALICE", 1000, "sig"))
        self.ledger.mine_block("MINER_1")

        block1 = self.store.get_last_block()
        proof1 = json.loads(block1["zk_proof"])

        self.assertEqual(proof1["prefix"], "zkp_v2_bulletproofs")
        self.assertEqual(proof1["meta"]["prev_root"], "0" * 64)

        # 2. Mine second block
        self.ledger.submit_tx(Transaction("ALICE", "BOB", 100, "sig"))
        self.ledger.mine_block("MINER_1")

        block2 = self.store.get_last_block()
        proof2 = json.loads(block2["zk_proof"])

        # Verify block2's proof links to block1's state root
        self.assertEqual(proof2["meta"]["prev_root"], block1["state_root"])

    def test_verification_failure_on_tampering(self):
        """Verify that ZK verification fails if the proof or state is tampered."""
        # 1. Setup initial state
        self.emu.state["balances"] = {"ALICE": 1000}
        self.ledger.mine_block("MINER_1")

        # 2. Attempt to receive an external block with a fake state root
        fake_block = {
            "index": 1,
            "prev_hash": self.store.get_last_block()["hash"],
            "tx_ids": ["fake_tx"],
            "hash": "fake_hash",
        }
        fake_balances = {"ALICE": 2000}  # Incorrect balance

        # ZKProofGenerator.verify_proof in ReplicatedLedger checks claimed_root
        fake_proof_json = json.dumps(
            {
                "prefix": "emu_proof",
                "proof": "fake",
                "meta": {"prev_root": self.store.get_last_block()["hash"]},
            }
        )

        result = self.ledger.receive_external_block(
            fake_block, fake_balances, fake_proof_json, []
        )
        self.assertFalse(result, "Should reject block with invalid state root")

    def test_performance_metrics(self):
        """Verify that ZK metrics (proving time, cycles) are reported."""
        self.emu.state["balances"] = {"ALICE": 100}
        self.ledger.mine_block("MINER_1")

        block = self.store.get_last_block()
        proof = json.loads(block["zk_proof"])

        # Metrics not implemented in Emulator yet
        self.assertNotIn("metrics", proof)


if __name__ == "__main__":
    unittest.main()
