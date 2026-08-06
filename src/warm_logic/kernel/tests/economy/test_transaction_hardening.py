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
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from warm_logic.kernel.economy.ledger import ReplicatedLedger, Transaction
from warm_logic.kernel.sys.persistence import SovereignStore


class TestTransactionHardening(unittest.TestCase):
    def setUp(self):
        # Use a temporary test database
        self.test_dir = Path("/tmp/warmlogic_test_era420")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True)
        self.db_path = self.test_dir / "test_sovereign.db"

        # Patch SovereignStore to use this path
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            self.store = SovereignStore(db_path=self.db_path)
        self.store._use_rust = False  # Force SQLite for forensic unit testing

        # [Brutal Truth] Replace MagicMock with high-fidelity Emulator
        from warm_logic.kernel.tests.emu.kernel_emu import KernelEmulator

        self.emu = KernelEmulator()

        # Patch loader to use our emulator
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_load:
                mock_load.return_value = self.emu
                self.ledger = ReplicatedLedger(store=self.store)

        # Sync emulator to ledger
        self.ledger.rust_core = self.emu
        self.ledger.store = self.store

    def tearDown(self):
        self.store.close()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_acid_atomic_transaction(self):
        """
        Verifies that state transitions are atomic.
        """
        # 1. Initialize balances
        self.store.commit_block(
            timestamp=0.0,
            tx_ids=[],
            miner="GENESIS",
            prev_hash="0" * 64,
            block_hash="genesis_hash",
            balance_updates={"ALICE": 1000, "BOB": 0},
        )

        self.emu.state["balances"] = {"ALICE": 1000, "BOB": 0}
        self.assertEqual(self.ledger.get_balance("ALICE"), 1000)
        self.assertEqual(self.ledger.get_balance("BOB"), 0)

        # 2. Submit transaction
        tx = Transaction(source="ALICE", target="BOB", amount=500, signature="sig1")
        self.assertTrue(self.ledger.submit_tx(tx))

        # 3. Mine block (Atomic transition)
        # Handle logic inside emulator for high-fidelity verification
        block_hash = self.ledger.mine_block("MINER")
        self.assertIsNotNone(block_hash)

        # 4. Verify updates
        self.assertEqual(self.ledger.get_balance("ALICE"), 500)
        self.assertEqual(self.ledger.get_balance("BOB"), 500)

    def test_state_root_determinism(self):
        """
        Verifies that state root is deterministic based on balances.
        """
        # Using emulator's deterministic state root
        self.store.commit_block(
            timestamp=0.0,
            tx_ids=[],
            miner="GENESIS",
            prev_hash="0" * 64,
            block_hash="h1",
            balance_updates={"A": 10, "B": 20},
        )
        root1 = self.ledger.get_state_root()

        # Clear and swap update order
        self.store.commit_block(
            timestamp=1.0,
            tx_ids=[],
            miner="GENESIS",
            prev_hash="h1",
            block_hash="h2",
            balance_updates={"B": 20, "A": 10},
        )
        root2 = self.ledger.get_state_root()

        self.assertEqual(root1, root2)


if __name__ == "__main__":
    unittest.main()
