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

# Ensure path is set (though runner handles this)
# from warm_logic.kernel.economy.ledger import ReplicatedLedger, Transaction


class TestLedgerSaturation(unittest.TestCase):
    """
    Perfection Saturation for ReplicatedLedger.
    Targets lines missed by standard mechanical tests.
    """

    def setUp(self):
        self.mock_store = MagicMock()
        self.mock_store.db_path = ":memory:"
        self.mock_store.get_balance.return_value = 100

        # We need to control HAS_RUST_CORE via patching in each test
        # or import it after patching.
        pass

    def test_init_rust_load_failure(self):
        """Cover lines 66-67: Rust init raises exception."""
        with patch("warm_logic.kernel.economy.ledger.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.economy.ledger.rust_loader.load_rust_core"
            ) as mock_load:
                mock_load.return_value.RustReplicatedLedger.side_effect = Exception(
                    "Rust Lib Fail"
                )

                from warm_logic.kernel.economy.ledger import ReplicatedLedger

                # Ensure store doesn't have shared ledger to force class init
                if hasattr(self.mock_store, "_rust_ledger"):
                    del self.mock_store._rust_ledger

                with self.assertRaises(RuntimeError) as cm:
                    ReplicatedLedger(self.mock_store)
                self.assertIn("Failed to initialize Rust Ledger", str(cm.exception))

    def test_legacy_submit_low_balance(self):
        """Cover submit_tx with error from Rust Core."""
        with patch("warm_logic.kernel.economy.ledger.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.economy.ledger.rust_loader.load_rust_core"
            ) as mock_load:
                mock_ledger = MagicMock()
                mock_load.return_value.RustReplicatedLedger.return_value = mock_ledger
                from warm_logic.kernel.economy.ledger import (
                    ReplicatedLedger,
                    Transaction,
                )

                # Ensure store doesn't have shared ledger to force class init
                if hasattr(self.mock_store, "_rust_ledger"):
                    del self.mock_store._rust_ledger

                ledger = ReplicatedLedger(self.mock_store)

                # Simulate Rust core rejecting transaction
                mock_ledger.submit_transaction.side_effect = Exception("Balance Low")

                tx = Transaction("A", "B", 20, "sig")
                result = ledger.submit_tx(tx)

                self.assertFalse(result)

    def test_receive_external_block_missing_keys(self):
        """Cover block missing index etc."""
        with patch("warm_logic.kernel.economy.ledger.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.economy.ledger.rust_loader.load_rust_core"
            ) as mock_load:
                mock_load.return_value.RustReplicatedLedger.return_value = MagicMock()
                from warm_logic.kernel.economy.ledger import ReplicatedLedger

                ledger = ReplicatedLedger(self.mock_store)

                bad_block = {"hash": "abc"}  # Missing index etc
                result = ledger.receive_external_block(bad_block, {}, "proof")
                self.assertFalse(result)

    def test_receive_external_block_slashing_db_error(self):
        """Cover lines 286-288: Slashing DB log fails."""
        with patch("warm_logic.kernel.economy.ledger.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.economy.ledger.rust_loader.load_rust_core"
            ) as mock_load:
                mock_load.return_value.RustReplicatedLedger.return_value = MagicMock()
                # 1. Force ZK fail
                with patch(
                    "warm_logic.kernel.substrate.proof_zk.ZKProofGenerator.verify_proof",
                    return_value=False,
                ):
                    from warm_logic.kernel.economy.ledger import ReplicatedLedger

            ledger = ReplicatedLedger(self.mock_store)

            # 2. Force DB error on slashing log
            # The code calls self.store.conn.execute
            self.mock_store.conn.execute.side_effect = Exception("DB Disk Full")

            block = {
                "index": 1,
                "prev_hash": "00",
                "tx_ids": [],
                "hash": "hh",
                "miner": "BAD_ACTOR",
            }
            result = ledger.receive_external_block(block, {}, "bad_proof")

            self.assertFalse(result)
            # Log error should be hit

    def test_receive_external_block_commit_error(self):
        """Cover commit block exception."""
        with patch("warm_logic.kernel.economy.ledger.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.economy.ledger.rust_loader.load_rust_core"
            ) as mock_load:
                mock_load.return_value.RustReplicatedLedger.return_value = MagicMock()
                with patch(
                    "warm_logic.kernel.substrate.proof_zk.ZKProofGenerator.verify_proof",
                    return_value=True,
                ):
                    from warm_logic.kernel.economy.ledger import ReplicatedLedger

                    ledger = ReplicatedLedger(self.mock_store)

                    self.mock_store.commit_block.side_effect = Exception("Commit Fail")

                    block = {"index": 1, "prev_hash": "00", "tx_ids": [], "hash": "hh"}
                    result = ledger.receive_external_block(block, {}, "proof")
                    self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
