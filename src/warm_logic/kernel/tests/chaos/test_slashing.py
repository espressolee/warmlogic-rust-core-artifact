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
import logging
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from warm_logic.kernel.economy.ledger import ReplicatedLedger
from warm_logic.kernel.sys.persistence import SovereignStore

# Setup logging
logging.basicConfig(level=logging.INFO)


class TestSlashingMechanism(unittest.TestCase):
    def setUp(self):
        self.db_path = "/tmp/test_slashing.db"
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()

        # Cleanup Sled DB if exists
        sled_path = Path("/tmp/sovereign_sled")
        if sled_path.exists():
            shutil.rmtree(sled_path)

        self.store = SovereignStore(self.db_path)
        # Force SQLite for forensic audit verification
        self.store._use_rust = False

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_load:
                self.mock_rs = MagicMock()
                mock_load.return_value.RustReplicatedLedger.return_value = self.mock_rs
                self.ledger = ReplicatedLedger(self.store)

    def tearDown(self):
        self.store.close()
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()

    def test_slashing_on_invalid_zk(self):
        # 1. Create a fake block that is invalid
        fake_block = {
            "index": 1,
            "prev_hash": "0000",
            "tx_ids": [],
            "hash": "FAKE",
            "miner": "MALICIOUS_NODE",
        }
        # Fake fake proof
        fake_proof = "invalid_proof"

        # 2. Receive it - but we need verify_proof to fail
        with patch("warm_logic.kernel.economy.ledger.ZKProofGenerator") as mock_zk:
            mock_zk.verify_proof.return_value = False
            result = self.ledger.receive_external_block(fake_block, {}, fake_proof, [])

        # 3. Assert Rejected
        self.assertFalse(result, "Block should be rejected")

        # 4. Assert Slashed
        # Check metadata table for SLASH record
        cursor = self.store.conn.execute(
            "SELECT key, value FROM metadata WHERE key LIKE 'SLASH:%'"
        )
        records = cursor.fetchall()
        self.assertTrue(len(records) > 0, "Offender should be slashed")
        self.assertIn("MALICIOUS_NODE", records[0][0])
        logging.info(f"Slashing Verified: {records[0]}")


if __name__ == "__main__":
    unittest.main()
