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
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.economy.ledger import ReplicatedLedger, Transaction
from warm_logic.kernel.sys.persistence import SovereignStore


class TestEconomy(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile

        self.test_dir = tempfile.mkdtemp()
        self.store = MagicMock(spec=SovereignStore)
        self.store.db_path = os.path.join(self.test_dir, "test.db")
        self.store.get_balance.return_value = 1000

        # Patch rust_loader for Ledger initialization
        self.patcher_has_rs = patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True)
        self.patcher_load_rs = patch("warm_logic.kernel.rust_loader.load_rust_core")
        self.patcher_has_rs.start()
        self.mock_load = self.patcher_load_rs.start()

        # Mock core to return a ledger instance mock
        self.mock_rs = MagicMock()
        self.mock_load.return_value = self.mock_rs
        self.mock_rs.RustReplicatedLedger.return_value.get_state_root.return_value = (
            "root"
        )

        self.ledger = ReplicatedLedger(self.store)

    def tearDown(self):
        self.patcher_has_rs.stop()
        self.patcher_load_rs.stop()

        import shutil

        # Close any potential connections if they existed
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_submit_tx_negative(self):
        tx = Transaction("A", "B", -1, "sig")
        self.assertFalse(self.ledger.submit_tx(tx))

    def test_transaction_id(self):
        tx = Transaction("A", "B", 100, "sig")
        self.assertTrue(len(tx.tx_id) == 64)

    def test_metal_submit(self):
        """Cover Rust delegation path (lines 78-88)"""
        # Inject Mock to force delegation path
        self.ledger.rust_core = MagicMock()

        tx = Transaction("A", "B", 10, "sig")
        self.assertTrue(self.ledger.submit_tx(tx))
        # Verify delegation
        self.ledger.rust_core.submit_transaction.assert_called_once()

    def test_receive_block_invalid(self):
        self.assertFalse(self.ledger.receive_external_block({}, {}, "proof"))

    def test_receive_block_zk_fail(self):
        from warm_logic.kernel.substrate.proof_zk import ZKProofGenerator

        with patch.object(ZKProofGenerator, "verify_proof", return_value=False):
            # Line 235: verify_proof False
            # Line 239: offender logic
            # Line 252: hasattr(self.store, 'conn')
            self.store.conn = MagicMock()
            block_data = {
                "index": 0,
                "prev_hash": "0",
                "tx_ids": [],
                "hash": "h",
                "miner": "M",
            }
            self.assertFalse(
                self.ledger.receive_external_block(block_data, {"A": 10}, "bad_proof")
            )

    def test_receive_block_exception(self):
        # Line 276: Commit exception
        self.store.commit_block.side_effect = Exception("DB Error")
        block_data = {"index": 0, "prev_hash": "0", "tx_ids": [], "hash": "h"}
        from warm_logic.kernel.substrate.proof_zk import ZKProofGenerator

        with patch.object(ZKProofGenerator, "verify_proof", return_value=True):
            self.assertFalse(
                self.ledger.receive_external_block(block_data, {}, "proof")
            )

    def test_slashing_exception(self):
        # Line 259: Slashing recording failure
        from warm_logic.kernel.substrate.proof_zk import ZKProofGenerator

        with patch.object(ZKProofGenerator, "verify_proof", return_value=False):
            self.store.conn = MagicMock()
            self.store.conn.execute.side_effect = Exception("SQL Error")
            block_data = {"index": 0, "prev_hash": "0", "tx_ids": [], "hash": "h"}
            self.assertFalse(
                self.ledger.receive_external_block(block_data, {}, "proof")
            )

    def test_mine_block_metal(self):
        # Line 126-151: mine_block Rust path
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            self.ledger.rust_core = MagicMock()
            self.ledger.rust_core.mine_block.return_value = "block_hash"
            mock_block = MagicMock()
            mock_block.transactions = [{"tx_id": "tx1"}]
            mock_block.tx_ids = ["tx1"]
            mock_block.miner = "miner_fixed"
            mock_block.timestamp = 1234.5
            mock_block.prev_hash = "prev"
            mock_block.hash = "block_hash"
            mock_block.zk_proof = "zkp"
            mock_block.state_root = "root"
            self.ledger.rust_core.get_last_block.return_value = mock_block
            self.ledger.rust_core.get_all_balances.return_value = {"alice": 100}

            self.ledger.mine_block("miner")
            self.store.commit_block.assert_called()


if __name__ == "__main__":
    unittest.main()
