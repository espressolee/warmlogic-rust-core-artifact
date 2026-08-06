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
import time
import unittest
from unittest import mock

from warm_logic.kernel.sys.persistence import SovereignStore
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestPersistence(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        self.db_path = self.get_temp_path("test_sovereign.db")
        self.store = SovereignStore(self.db_path)

    def tearDown(self):
        self.store.close()
        super().tearDown()

    def test_init_default(self):
        # Line 22-23: Default path logic
        with mock.patch("warm_logic.kernel.sys.persistence.Path") as mock_path:
            mock_root = mock.MagicMock()
            mock_root.__truediv__.return_value = mock_root
            mock_root.resolve.return_value = mock_root
            mock_path.return_value = mock_root
            # Trigger init with None
            SovereignStore(None)

    def test_meta_ops(self):
        # Line 145-146, 155-159: set_meta, get_meta
        self.store.set_meta("config_v1", {"pqc_active": True})
        val = self.store.get_meta("config_v1")
        self.assertEqual(val["pqc_active"], True)

        self.assertIsNone(self.store.get_meta("non_existent"))

    def test_meta_ops_tolerates_non_json_rows(self):
        # SQLite can contain typed/raw values if written outside set_meta.
        self.store.conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("budget_last_reset", 1234.5),
        )
        self.store.conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("genesis_hash", "h1"),
        )
        self.store.conn.commit()

        self.assertEqual(self.store.get_meta("budget_last_reset"), 1234.5)
        self.assertEqual(self.store.get_meta("genesis_hash"), "h1")

    def test_event_logging(self):
        # Line 109-125, 131-135, 141-142
        ts = time.time()
        payload = {"tick": 100}
        self.store.log_event(ts, "TICK", payload, "PREV", "CURR", "ROOT", "PROOF")

        last = self.store.get_last_event()
        self.assertEqual(last["hash"], "CURR")
        self.assertEqual(last["event_type"], "TICK")

        all_events = self.store.get_all_events()
        self.assertEqual(len(all_events), 1)

    def test_economy_ops(self):
        # Line 161-166, 172-205, 214-218: get_balance, commit_block, get_last_block
        self.store.commit_block(
            timestamp=time.time(),
            tx_ids=["tx1", "tx2"],
            miner="miner_a",
            prev_hash="0000",
            block_hash="b1",
            balance_updates={"alice": 500, "bob": 200},
            zk_proof="zk1",
            state_root="root_x",
        )

        self.assertEqual(self.store.get_balance("alice"), 500)
        self.assertEqual(self.store.get_balance("bob"), 200)
        self.assertEqual(self.store.get_balance("charlie"), 0)

        all_b = self.store.get_all_balances()
        self.assertEqual(all_b["alice"], 500)

        last_b = self.store.get_last_block()
        self.assertEqual(last_b["hash"], "b1")
        self.assertEqual(last_b["state_root"], "root_x")

    def test_ensure_init_branches(self):
        # Line 81-93: Migration logic
        # 1. Create a "Legacy" DB without columns
        legacy_db = self.get_temp_path("legacy.db")
        import sqlite3

        conn = sqlite3.connect(legacy_db)
        conn.execute(
            "CREATE TABLE ledger (id INTEGER PRIMARY KEY, timestamp REAL, event_type TEXT, payload JSON, prev_hash TEXT, hash TEXT)"
        )
        conn.execute(
            "CREATE TABLE blocks (id INTEGER PRIMARY KEY, timestamp REAL, tx_ids TEXT, miner TEXT, prev_hash TEXT, hash TEXT UNIQUE)"
        )
        conn.close()

        # 2. Open with SovereignStore to trigger ALTER
        store = SovereignStore(legacy_db)
        store.set_meta("migration", "done")

        # Verify columns added
        cursor = store.conn.execute("PRAGMA table_info(blocks)")
        cols = [r["name"] for r in cursor.fetchall()]
        self.assertIn("state_root", cols)

        store.close()

    def test_get_last_event_empty(self):
        # Line 135: return None
        empty_db = self.get_temp_path("empty.db")
        store = SovereignStore(empty_db)
        self.assertIsNone(store.get_last_event())
        store.close()

    def test_rust_path_mocked(self):
        """Verify the Rust path logic by mocking the Rust module."""
        # 1. Patch HAS_RUST_CORE to True
        with mock.patch(
            "warm_logic.kernel.sys.persistence.rust_loader.HAS_RUST_CORE", True
        ):
            # 2. Mock the Rust module functions
            with mock.patch(
                "warm_logic.kernel.sys.persistence.rust_loader.load_rust_core"
            ) as mock_load:
                mock_core = mock.MagicMock()
                mock_load.return_value = mock_core

                # Mock Rust Store methods
                # Mock Rust Store methods
                mock_sled = mock.MagicMock()
                mock_core.SovereignStore.return_value = mock_sled
                mock_ledger_instance = mock.MagicMock()
                mock_core.RustReplicatedLedger.return_value = mock_ledger_instance

                # Setup return values
                mock_sled.get.return_value = '{"rust": "meta"}'
                mock_ledger_instance.get_balance.return_value = 999

                # Initialize Store (should trigger Rust path)
                store = SovereignStore(self.db_path)

                # Verify Rust methods called

                # set_meta uses Rust
                store.set_meta("k", {"v": 1})
                mock_sled.put.assert_called()

                # get_meta uses Rust
                meta = store.get_meta("k")
                self.assertEqual(meta, {"rust": "meta"})

                # get_balance uses Rust
                bal = store.get_balance("addr")
                self.assertEqual(bal, 999)

                store.close()

    def test_rust_path_errors(self):
        """Verify Rust path exception handling."""
        with mock.patch(
            "warm_logic.kernel.sys.persistence.rust_loader.HAS_RUST_CORE", True
        ):
            with mock.patch(
                "warm_logic.kernel.sys.persistence.rust_loader.load_rust_core"
            ) as mock_load:
                mock_core = mock.MagicMock()
                mock_load.return_value = mock_core

                # Mock generic structure
                mock_sled = mock.MagicMock()
                mock_core.SovereignStore.return_value = mock_sled
                mock_ledger_instance = mock.MagicMock()
                mock_core.RustReplicatedLedger.return_value = mock_ledger_instance

                store = SovereignStore(self.db_path)

                # Test set_meta error - Rust fails but SQLite should still work
                mock_sled.put.side_effect = Exception("Rust Put Error")
                # Should catch exception and log error, not crash
                store.set_meta("k", "v")

                # Test get_meta error - Rust fails but SQLite fallback returns value
                mock_sled.get.side_effect = Exception("Rust Get Error")
                val = store.get_meta("k")
                # SQLite fallback should still return the value
                self.assertEqual(val, "v")

                # Test get_balance error
                mock_ledger_instance.get_balance.side_effect = Exception(
                    "Rust Bal Error"
                )
                bal = store.get_balance("x")
                self.assertEqual(bal, 0)

                # Test get_last_block error
                mock_ledger_instance.get_last_block.side_effect = Exception(
                    "Rust Block Error"
                )
                lb = store.get_last_block()
                self.assertIsNone(lb)

                store.close()

    def test_rust_get_last_block(self):
        with mock.patch(
            "warm_logic.kernel.sys.persistence.rust_loader.HAS_RUST_CORE", True
        ):
            with mock.patch(
                "warm_logic.kernel.sys.persistence.rust_loader.load_rust_core"
            ) as mock_load:
                mock_core = mock.MagicMock()
                mock_load.return_value = mock_core

                mock_ledger = mock.MagicMock()
                mock_core.RustReplicatedLedger.return_value = mock_ledger
                # Need to mock the returned block object structure
                mock_block = mock.MagicMock()
                mock_block.timestamp = 1.0
                mock_block.tx_ids = []
                mock_block.miner = "m"
                mock_block.prev_hash = "ph"
                mock_block.hash = "h"
                mock_block.zk_proof = "zk"

                mock_ledger.get_last_block.return_value = mock_block

                store = SovereignStore(self.db_path)
                lb = store.get_last_block()
                self.assertEqual(lb["hash"], "h")
                self.assertEqual(lb["zk_proof"], "zk")
                store.close()

    def test_init_rust_failure(self):
        """Verify RuntimeError if Rust init fails (No fallback)."""
        with mock.patch(
            "warm_logic.kernel.sys.persistence.rust_loader.HAS_RUST_CORE", True
        ):
            with mock.patch(
                "warm_logic.kernel.sys.persistence.rust_loader.load_rust_core"
            ) as mock_load:
                mock_core = mock.MagicMock()
                mock_load.return_value = mock_core

                # redb init failure
                mock_core.SovereignStore.side_effect = Exception("redb Init Failed")

                with self.assertRaises(RuntimeError) as cm:
                    SovereignStore(self.db_path)

                self.assertIn("redb Init Failed", str(cm.exception))

    def test_get_last_block_empty(self):
        # Empty DB, Python path
        store = SovereignStore(self.get_temp_path("nb.db"))
        self.assertIsNone(store.get_last_block())
        store.close()

    def test_blob_ops(self):
        """Cover put_blob and get_blob (Python + Rust paths)."""
        # 1. Python Path (SQLite meta reuse)
        blob_data = b"\xde\xad\xbe\xef"
        self.store.put_blob("blob_key", blob_data)

        # Verify direct retrieval
        self.assertEqual(self.store.get_blob("blob_key"), blob_data)

        # Verify fallback string encoding handling using json dump
        str_blob = "string_data"
        self.store.put_blob("str_key", str_blob)
        # get_blob returns bytes if it was stored as string but get_blob logic
        # tries to fromhex. If not hex, it encodes utf-8.
        # "string_data" is not hex.
        self.assertEqual(self.store.get_blob("str_key"), b"string_data")

        # 2. Rust Path Mocked
        with mock.patch(
            "warm_logic.kernel.sys.persistence.rust_loader.HAS_RUST_CORE", True
        ):
            with mock.patch(
                "warm_logic.kernel.sys.persistence.rust_loader.load_rust_core"
            ) as mock_load:
                mock_core = mock.MagicMock()
                mock_load.return_value = mock_core
                mock_store = mock.MagicMock()
                mock_core.SovereignStore.return_value = mock_store

                # Init with rust
                store_rust = SovereignStore(self.db_path)

                # Put Blob
                store_rust.put_blob("r_blob", b"\x00")
                mock_store.put.assert_called()

                # Get Blob (Rust returns hex string or raw string? Code assumes it returns something)
                # Code: val_str = self._rust_store.get(key)
                mock_store.get.return_value = "deadbeef"
                val = store_rust.get_blob("r_blob")
                self.assertEqual(val, b"\xde\xad\xbe\xef")

                store_rust.close()

    def test_reconcile_state(self):
        """Cover reconcile_state logic."""
        # 1. Skip if no Rust
        # Default store has _use_rust=False
        self.assertFalse(self.store.reconcile_state())

        # 2. Mock Rust for Success Path
        with mock.patch(
            "warm_logic.kernel.sys.persistence.rust_loader.HAS_RUST_CORE", True
        ):
            with mock.patch(
                "warm_logic.kernel.sys.persistence.rust_loader.load_rust_core"
            ) as mock_load:
                mock_core = mock.MagicMock()
                mock_load.return_value = mock_core
                mock_ledger = mock.MagicMock()
                mock_core.RustReplicatedLedger.return_value = mock_ledger

                # Setup sync_state method on mock
                mock_ledger.sync_state = mock.MagicMock()

                store_rust = SovereignStore(self.db_path)

                # Pre-populate SQLite with some data to sync
                store_rust.update_balance("alice", 1000)
                store_rust.commit_block(1.0, [], "miner", "p", "h", {})

                # Run reconcile
                res = store_rust.reconcile_state()
                self.assertTrue(res)
                mock_ledger.sync_state.assert_called()

                # 3. Fail path (Exception)
                mock_ledger.sync_state.side_effect = Exception("Sync Fail")
                res_fail = store_rust.reconcile_state()
                self.assertFalse(res_fail)

                # 4. No sync_state method
                del mock_ledger.sync_state
                res_nosync = store_rust.reconcile_state()
                self.assertFalse(res_nosync)

                store_rust.close()

    def test_update_balance_direct(self):
        """Cover direct update_balance."""
        self.store.update_balance("target", 999)
        val = self.store.get_balance("target")
        self.assertEqual(val, 999)

        # Verify Rust path call
        with mock.patch(
            "warm_logic.kernel.sys.persistence.rust_loader.HAS_RUST_CORE", True
        ):
            with mock.patch(
                "warm_logic.kernel.sys.persistence.rust_loader.load_rust_core"
            ) as mock_load:
                mock_core = mock.MagicMock()
                mock_load.return_value = mock_core
                store_rust = SovereignStore(self.db_path)

                # It should log error if rust fails or pass silently if implemented
                # Current code: pass in try/except
                store_rust.update_balance("t", 1)
                store_rust.close()


if __name__ == "__main__":
    unittest.main()
