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
from unittest import mock

from warm_logic.kernel.economy.ledger import ReplicatedLedger, Transaction
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestReplicatedLedger(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        self.db_path = self.get_temp_path("test_ledger.db")

        # Mock Store (we don't need real store for ledger tests, mocks are better)
        self.mock_store = mock.MagicMock()
        self.mock_store.db_path = self.db_path
        self.mock_store._rust_ledger = None

        # Patch Rust Loader for all tests in this class
        self.rust_patcher = mock.patch(
            "warm_logic.kernel.economy.ledger.rust_loader.HAS_RUST_CORE", True
        )
        self.rust_patcher.start()

        self.load_patcher = mock.patch(
            "warm_logic.kernel.economy.ledger.rust_loader.load_rust_core"
        )
        self.mock_load = self.load_patcher.start()

        # Mock Rust Core
        self.mock_rs = mock.MagicMock()
        self.mock_load.return_value = self.mock_rs

        self.mock_core_instance = mock.MagicMock()
        self.mock_rs.RustReplicatedLedger.return_value = self.mock_core_instance

        self.ledger = ReplicatedLedger(store=self.mock_store)

    def tearDown(self):
        self.rust_patcher.stop()
        self.load_patcher.stop()
        super().tearDown()

    def test_submit_tx(self):
        tx = Transaction("Alice", "Bob", 100, "sig")
        self.mock_core_instance.submit_transaction.return_value = (
            None  # returns void in rust
        )

        res = self.ledger.submit_tx(tx)

        self.assertTrue(res)
        self.mock_core_instance.submit_transaction.assert_called_with(
            tx.tx_id, "Alice", "Bob", 100, "sig", tx.timestamp, 20, 1
        )

    def test_submit_tx_negative(self):
        tx = Transaction("Alice", "Bob", -10, "sig")
        res = self.ledger.submit_tx(tx)
        self.assertFalse(res)
        self.mock_core_instance.submit_transaction.assert_not_called()

    def test_submit_tx_failure(self):
        tx = Transaction("Alice", "Bob", 100, "sig")
        self.mock_core_instance.submit_transaction.side_effect = Exception("Invalid")

        res = self.ledger.submit_tx(tx)
        self.assertFalse(res)

    def test_mine_block_success(self):
        # Setup mocks
        self.mock_core_instance.mine_block.return_value = "new_hash"
        self.mock_core_instance.get_last_block.return_value = mock.MagicMock(
            timestamp=1.0,
            tx_ids=["t1"],
            miner="m1",
            prev_hash="ph",
            hash="new_hash",
            zk_proof="zk",
            state_root="sr",
        )
        self.mock_core_instance.get_all_balances.return_value = {"Alice": 100}

        res = self.ledger.mine_block("m1")

        self.assertEqual(res, "new_hash")
        # Verify Store Commit
        self.mock_store.commit_block.assert_called_once()
        args, kwargs = self.mock_store.commit_block.call_args
        self.assertEqual(kwargs["state_root"], "sr")
        self.assertEqual(kwargs["balance_updates"], {"Alice": 100})

    def test_mine_block_failure(self):
        self.mock_core_instance.mine_block.return_value = None
        res = self.ledger.mine_block("m1")
        self.assertIsNone(res)
        self.mock_store.commit_block.assert_not_called()

    def test_helpers(self):
        # get_balance
        self.mock_core_instance.get_balance.return_value = 50
        self.assertEqual(self.ledger.get_balance("A"), 50)

        self.mock_core_instance.get_balance.side_effect = Exception("Err")
        self.assertEqual(self.ledger.get_balance("A"), 0)

        # get_state_root
        self.mock_core_instance.get_state_root.return_value = "root"
        self.assertEqual(self.ledger.get_state_root(), "root")

        self.mock_core_instance.get_state_root.side_effect = Exception("Err")
        self.assertEqual(self.ledger.get_state_root(), "0")

    def test_close(self):
        self.ledger.close()
        self.mock_store.close.assert_called()
        self.assertIsNone(self.ledger.rust_core)

    def test_init_failures(self):
        # 1. Missing Rust Core
        with mock.patch(
            "warm_logic.kernel.economy.ledger.rust_loader.HAS_RUST_CORE", False
        ):
            with self.assertRaises(RuntimeError) as cm:
                ReplicatedLedger(self.mock_store)
            self.assertIn("Rust Core missing", str(cm.exception))

        # 2. Rust Init Failure
        # We need to stop the class-level patcher briefly or override it?
        # self.rust_patcher patches to True.
        # The inner patch needs to set load_chunk to fail.

        self.mock_load.side_effect = Exception("Load Fail")

        # We need to re-init ledger, but we are inside an instance where setUp already ran.
        # We can just try to init a new one.
        with self.assertRaises(RuntimeError) as cm:
            ReplicatedLedger(self.mock_store)
        self.assertIn("Failed to initialize Rust Ledger", str(cm.exception))

        # Reset side_effect for other tests if needed (though tearDown handles it)
        self.mock_load.side_effect = None

    def test_consensus_callback(self):
        cb = mock.MagicMock()
        ledger = ReplicatedLedger(self.mock_store, consensus_callback=cb)

        # Setup mine_block success
        self.mock_core_instance.mine_block.return_value = "h"
        self.mock_core_instance.get_last_block.return_value = mock.MagicMock(
            timestamp=1.0,
            tx_ids=[],
            miner="m",
            prev_hash="p",
            hash="h",
            zk_proof="z",
            state_root="r",
        )
        self.mock_core_instance.get_all_balances.return_value = {}

        ledger.mine_block("m")
        cb.assert_called_once()

    def test_receive_external_block(self):
        # 1. basic validation fail
        res = self.ledger.receive_external_block({}, {}, "proof")
        self.assertFalse(res)

        # 2. ZK Verify Fail
        # Need to mock ZKProofGenerator
        block = {"index": 1, "prev_hash": "ph", "tx_ids": [], "hash": "h"}

        with mock.patch("warm_logic.kernel.economy.ledger.ZKProofGenerator") as mock_zk:
            mock_zk.verify_proof.return_value = False
            res = self.ledger.receive_external_block(block, {}, "proof")
            self.assertFalse(res)

            # 3. Success
            mock_zk.verify_proof.return_value = True
            res = self.ledger.receive_external_block(block, {}, "proof")
            self.assertTrue(res)
            self.mock_store.commit_block.assert_called()

            # 4. Commit Fail
            self.mock_store.commit_block.side_effect = Exception("Commit Fail")
            res = self.ledger.receive_external_block(block, {}, "proof")
            self.assertFalse(res)

    def test_tx_id_integrity(self):
        tx = Transaction("A", "B", 10, "sig", timestamp=123.45)
        # Determine actual hash based on implementation details if needed,
        # but here we just ensure it returns a string of correct length
        self.assertEqual(len(tx.tx_id), 64)


if __name__ == "__main__":
    unittest.main()
