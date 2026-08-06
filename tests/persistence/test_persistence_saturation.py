import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import warm_logic.kernel.rust_loader as rust_loader
from warm_logic.kernel.sys.persistence import SovereignStore


class TestPersistenceSaturation:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test.db"
        yield
        self.tmp_dir.cleanup()

    def test_init_with_env_root(self):
        """Test initialization using SOVEREIGN_STORE_ROOT."""
        with tempfile.TemporaryDirectory() as env_dir:
            with patch.dict(os.environ, {"SOVEREIGN_STORE_ROOT": env_dir}):
                store = SovereignStore()
                assert (
                    store.db_path
                    == Path(env_dir).resolve() / ".sovereign" / "sovereign.db"
                )
                store.close()

    def test_init_rust_failure(self):
        """Test that redb initialization failure raises RuntimeError."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_load:
                mock_rs = MagicMock()
                mock_rs.SovereignStore.side_effect = Exception("redb Panic")
                mock_load.return_value = mock_rs

                with pytest.raises(
                    RuntimeError, match="Persistence Hardening: redb Init Failed"
                ):
                    SovereignStore(self.db_path)

    def test_schema_migration(self):
        """Test schema migration by initializing on a legacy database."""
        # Create a partial database
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE blocks (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        # SovereignStore should detect missing columns and ALTER TABLE
        store = SovereignStore(self.db_path)

        # Verify columns exist now
        cursor = store.conn.execute("PRAGMA table_info(ledger)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "state_root" in columns
        assert "zk_proof" in columns

        cursor = store.conn.execute("PRAGMA table_info(blocks)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "index" in columns
        assert "tx_ids" in columns
        store.close()

    def test_log_event_no_conn(self):
        """Test log_event failure when connection is missing."""
        store = SovereignStore(self.db_path)
        store.conn = None
        with pytest.raises(RuntimeError, match="Database connection not initialized"):
            store.log_event(1.0, "TEST", {}, "prev", "curr")
        store.close()

    def test_get_last_event_no_conn(self):
        """Test get_last_event returns None if connection is missing."""
        store = SovereignStore(self.db_path)
        store.conn = None
        assert store.get_last_event() is None
        store.close()

    def test_get_all_events_no_conn(self):
        """Test get_all_events returns empty list if connection is missing."""
        store = SovereignStore(self.db_path)
        store.conn = None
        assert store.get_all_events() == []
        store.close()

    def test_rust_store_failures(self):
        """Saturate error paths in set_meta and get_meta when Rust fails."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            # We use a mock that throws
            mock_rs_store = MagicMock()
            mock_rs_store.put.side_effect = Exception("Rust Error")
            mock_rs_store.get.side_effect = Exception("Rust Error")

            with patch("warm_logic.kernel.rust_loader.load_rust_core"):
                # Setup store to use our failing mock
                store = SovereignStore(self.db_path)
                store._rust_store = mock_rs_store

                # Should not raise, should log error and continue to SQLite
                store.set_meta("key_fail", "val_fail")
                assert store.get_meta("key_fail") == "val_fail"  # Fetched from SQLite
                store.close()

    def test_balance_sqlite_fallback(self):
        """Test get_balance falls back to SQLite if Rust returns 0."""
        store = SovereignStore(self.db_path)
        # Manually inject SQLite balance
        store.conn.execute(
            "INSERT INTO balances (address, amount) VALUES ('addr1', 500)"
        )
        store.conn.commit()

        # Ensure Rust returns 0 to trigger fallback
        store._use_rust = True
        store._rust_ledger = MagicMock()
        store._rust_ledger.get_balance.return_value = 0

        # Should fallback to SQLite
        assert store.get_balance("addr1") == 500
        store.close()

    def test_get_last_block_failures(self):
        """Test get_last_block error handling."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        store._rust_ledger = MagicMock()
        store._rust_ledger.get_last_block.side_effect = Exception("Rust Failure")

        assert store.get_last_block() is None
        store.close()

    def test_get_block_failures(self):
        """Test get_block error handling."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        store._rust_ledger = MagicMock()
        store._rust_ledger.get_block.side_effect = Exception("Rust Failure")

        assert store.get_block("hash") is None
        store.close()

    def test_blob_failures(self):
        """Test put_blob and get_blob error handling."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        store._rust_store = MagicMock()
        store._rust_store.put.side_effect = Exception("Rust Failure")
        store._rust_store.get.side_effect = Exception("Rust Failure")

        store.put_blob("b1", b"data")
        # Should fallback to SQLite
        assert store.get_blob("b1") == b"data"
        store.close()

    def test_reconcile_state_no_rust_ledger(self):
        """Test reconcile_state when Rust ledger is not active (edge case)."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        store._rust_ledger = None
        assert store.reconcile_state() is False
        store.close()

    def test_reconcile_state_no_rust_at_all(self):
        """Test reconcile_state when use_rust is False."""
        store = SovereignStore(self.db_path)
        store._use_rust = False
        assert store.reconcile_state() is False
        store.close()

    def test_reconcile_state_success(self):
        """Test successful state reconciliation."""
        store = SovereignStore(self.db_path)
        # Load some data into SQLite
        store.update_balance("addr_rec", 1000)
        store.commit_block(1.0, [], "miner", "prev", "h1", {"addr_rec": 1000})

        store._use_rust = True
        mock_ledger = MagicMock()
        # Mocking sync_state existence
        mock_ledger.sync_state = MagicMock()
        store._rust_ledger = mock_ledger

        assert store.reconcile_state() is True
        mock_ledger.sync_state.assert_called_once()
        store.close()

    def test_reconcile_state_no_sync_state(self):
        """Test reconcile_state when Rust ledger lacks sync_state."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        store._rust_ledger = MagicMock(spec=[])  # No attributes

        assert store.reconcile_state() is False
        store.close()

    def test_reconcile_state_exception(self):
        """Test reconcile_state during exception."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        store._rust_ledger = MagicMock()
        store._rust_ledger.sync_state.side_effect = Exception("Critical Sync Error")

        assert store.reconcile_state() is False
        store.close()

    def test_get_blob_non_hex(self):
        """Test get_blob fallback for non-hex strings."""
        store = SovereignStore(self.db_path)
        # Manually insert non-hex string into SQLite
        store.conn.execute(
            "INSERT INTO metadata (key, value) VALUES ('raw', '\"not hex\"')"
        )
        store.conn.commit()

        assert store.get_blob("raw") == b"not hex"
        store.close()

    def test_get_blob_magicmock(self):
        """Test get_blob with non-string/non-bytes value (coverage for lines 459-461)."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        # Mock returning an object of unknown type
        store._rust_store = MagicMock()
        store._rust_store.get.return_value = 12345

        assert store.get_blob("mock") is None
        store.close()
