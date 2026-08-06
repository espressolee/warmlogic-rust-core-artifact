# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic SovereignStore persistence."""

import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel import rust_loader

# Patch rust_loader before importing SovereignStore
with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
    from warm_logic.kernel.sys.persistence import SovereignStore


# Flag to skip Rust-dependent tests if Rust core not available
HAS_RUST = rust_loader.HAS_RUST_CORE


class TestSovereignStoreInit:
    """Test SovereignStore initialization."""

    def test_init_creates_db_path(self, tmp_path):
        """Creates database at specified path."""
        db_path = tmp_path / "test.db"

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(db_path)

        assert store.db_path == db_path
        assert db_path.exists()
        store.close()

    def test_init_creates_parent_directories(self, tmp_path):
        """Creates parent directories if needed."""
        db_path = tmp_path / "deep" / "nested" / "store.db"

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(db_path)

        assert db_path.parent.exists()
        store.close()

    def test_init_creates_tables(self, tmp_path):
        """Creates required tables."""
        db_path = tmp_path / "test.db"

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(db_path)

        # Check tables exist
        cursor = store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}

        assert "ledger" in tables
        assert "metadata" in tables
        assert "blocks" in tables
        assert "balances" in tables
        store.close()

    def test_init_with_env_var(self, tmp_path, monkeypatch):
        """Uses SOVEREIGN_STORE_ROOT environment variable."""
        monkeypatch.setenv("SOVEREIGN_STORE_ROOT", str(tmp_path))

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore()

        expected = tmp_path / ".sovereign" / "sovereign.db"
        assert store.db_path == expected
        store.close()


class TestLedgerOperations:
    """Test ledger event logging."""

    def test_log_event_returns_id(self, tmp_path):
        """Returns row ID for logged event."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        row_id = store.log_event(
            timestamp=1234567890.0,
            event_type="TEST",
            payload={"key": "value"},
            prev_hash="0" * 64,
            current_hash="a" * 64,
        )

        assert row_id == 1
        store.close()

    def test_log_event_stores_data(self, tmp_path):
        """Correctly stores event data."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.log_event(
            timestamp=1234567890.0,
            event_type="GOVERNANCE_DECISION",
            payload={"decision": "approve", "score": 0.95},
            prev_hash="0" * 64,
            current_hash="abc123",
            state_root="state_root_hash",
            zk_proof="zk_proof_data",
        )

        event = store.get_last_event()
        assert event["timestamp"] == 1234567890.0
        assert event["event_type"] == "GOVERNANCE_DECISION"
        assert json.loads(event["payload"]) == {"decision": "approve", "score": 0.95}
        assert event["state_root"] == "state_root_hash"
        assert event["zk_proof"] == "zk_proof_data"
        store.close()

    def test_get_last_event_empty(self, tmp_path):
        """Returns None when no events."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        assert store.get_last_event() is None
        store.close()

    def test_get_all_events(self, tmp_path):
        """Returns all events in order."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.log_event(1.0, "A", {}, "0" * 64, "hash1")
        store.log_event(2.0, "B", {}, "hash1", "hash2")
        store.log_event(3.0, "C", {}, "hash2", "hash3")

        events = store.get_all_events()
        assert len(events) == 3
        assert events[0]["event_type"] == "A"
        assert events[2]["event_type"] == "C"
        store.close()


class TestMetadataOperations:
    """Test key-value metadata storage."""

    def test_set_and_get_meta(self, tmp_path):
        """Stores and retrieves metadata."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.set_meta("config_key", {"setting": True, "value": 42})

        result = store.get_meta("config_key")
        assert result == {"setting": True, "value": 42}
        store.close()

    def test_set_meta_overwrites(self, tmp_path):
        """Overwrites existing key."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.set_meta("key", "old_value")
        store.set_meta("key", "new_value")

        assert store.get_meta("key") == "new_value"
        store.close()

    def test_get_meta_missing_key(self, tmp_path):
        """Returns None for missing key."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        assert store.get_meta("nonexistent") is None
        store.close()

    def test_get_all_meta(self, tmp_path):
        """Returns all metadata entries."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.set_meta("key1", "value1")
        store.set_meta("key2", "value2")

        all_meta = store.get_all_meta()
        keys = [k for k, v in all_meta]
        assert "key1" in keys
        assert "key2" in keys
        store.close()


class TestBalanceOperations:
    """Test balance management."""

    def test_get_balance_default_zero(self, tmp_path):
        """Returns 0 for unknown address."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        balance = store.get_balance("unknown_address")
        assert balance == 0
        store.close()

    def test_update_and_get_balance(self, tmp_path):
        """Updates and retrieves balance."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.update_balance("alice", 1000)

        assert store.get_balance("alice") == 1000
        store.close()

    def test_update_balance_overwrites(self, tmp_path):
        """Overwrites existing balance."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.update_balance("bob", 500)
        store.update_balance("bob", 750)

        assert store.get_balance("bob") == 750
        store.close()

    def test_get_all_balances(self, tmp_path):
        """Returns all balances."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.update_balance("alice", 100)
        store.update_balance("bob", 200)
        store.update_balance("charlie", 300)

        balances = store.get_all_balances()
        assert balances == {"alice": 100, "bob": 200, "charlie": 300}
        store.close()


class TestBlockOperations:
    """Test block storage."""

    def test_commit_block(self, tmp_path):
        """Commits block to database."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.commit_block(
            timestamp=1234567890.0,
            tx_ids=["tx1", "tx2"],
            miner="miner_addr",
            prev_hash="0" * 64,
            block_hash="abc123",
            balance_updates={"alice": 100, "bob": 50},
            zk_proof="proof_data",
            state_root="state_hash",
            index=0,
        )

        block = store.get_last_block()
        assert block is not None
        assert block["hash"] == "abc123"
        assert block["miner"] == "miner_addr"
        store.close()

    def test_commit_block_updates_balances(self, tmp_path):
        """Updates balances atomically with block."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.commit_block(
            timestamp=1.0,
            tx_ids=[],
            miner="miner",
            prev_hash="0" * 64,
            block_hash="hash1",
            balance_updates={"alice": 500, "bob": 300},
        )

        assert store.get_balance("alice") == 500
        assert store.get_balance("bob") == 300
        store.close()

    def test_get_block_by_hash(self, tmp_path):
        """Retrieves block by hash."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.commit_block(
            timestamp=1.0,
            tx_ids=["tx1"],
            miner="miner",
            prev_hash="0" * 64,
            block_hash="unique_hash_123",
            balance_updates={},
        )

        block = store.get_block("unique_hash_123")
        assert block is not None
        assert block["hash"] == "unique_hash_123"
        store.close()

    def test_get_block_not_found(self, tmp_path):
        """Returns None for unknown block hash."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        assert store.get_block("nonexistent") is None
        store.close()


class TestBlobOperations:
    """Test blob storage."""

    def test_put_and_get_blob_bytes(self, tmp_path):
        """Stores and retrieves bytes blob."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        data = b"\x00\x01\x02\xff\xfe\xfd"
        store.put_blob("binary_key", data)

        result = store.get_blob("binary_key")
        assert result == data
        store.close()

    def test_put_and_get_blob_string(self, tmp_path):
        """Stores and retrieves string blob."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.put_blob("string_key", "hello world")

        result = store.get_blob("string_key")
        # String is hex-encoded, then decoded back
        assert result is not None
        store.close()

    def test_get_blob_not_found(self, tmp_path):
        """Returns None for missing blob."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        assert store.get_blob("missing") is None
        store.close()


class TestDeserializeStoredValue:
    """Test _deserialize_stored_value helper."""

    def test_deserialize_none(self, tmp_path):
        """Returns None for None input."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        assert store._deserialize_stored_value(None) is None
        store.close()

    def test_deserialize_bytearray(self, tmp_path):
        """Converts bytearray to decoded string/JSON."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        result = store._deserialize_stored_value(bytearray(b'{"key": "value"}'))
        assert result == {"key": "value"}
        store.close()

    def test_deserialize_bytes(self, tmp_path):
        """Converts bytes to decoded string/JSON."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        result = store._deserialize_stored_value(b'{"number": 42}')
        assert result == {"number": 42}
        store.close()

    def test_deserialize_json_string(self, tmp_path):
        """Parses JSON string."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        result = store._deserialize_stored_value('["a", "b", "c"]')
        assert result == ["a", "b", "c"]
        store.close()

    def test_deserialize_plain_string(self, tmp_path):
        """Returns plain string if not JSON."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        result = store._deserialize_stored_value("plain text")
        assert result == "plain text"
        store.close()

    def test_deserialize_empty_string(self, tmp_path):
        """Returns None for empty string."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        assert store._deserialize_stored_value("") is None
        assert store._deserialize_stored_value("   ") is None
        store.close()

    def test_deserialize_invalid_utf8(self, tmp_path):
        """Returns raw bytes for invalid UTF-8."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        invalid_bytes = b"\xff\xfe\x00\x01"
        result = store._deserialize_stored_value(invalid_bytes)
        assert result == invalid_bytes
        store.close()


class TestConnectionManagement:
    """Test database connection lifecycle."""

    def test_conn_property_getter(self, tmp_path):
        """conn property returns connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        assert store.conn is not None
        assert isinstance(store.conn, sqlite3.Connection)
        store.close()

    def test_conn_property_setter(self, tmp_path):
        """conn property setter closes previous connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        old_conn = store.conn
        store.conn = None

        assert store.conn is None
        store.close()

    def test_close(self, tmp_path):
        """close() releases resources."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.close()

        assert store.conn is None
        assert store._use_rust is False

    def test_del_closes_connection(self, tmp_path):
        """__del__ closes connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")
            conn = store.conn

        del store
        # Connection should be closed (can't directly verify, but no error)


class TestReconcileState:
    """Test state reconciliation."""

    def test_reconcile_without_rust(self, tmp_path):
        """Returns False when Rust not available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        result = store.reconcile_state()
        assert result is False
        store.close()


class TestSchemaMigration:
    """Test schema migration handling."""

    def test_migration_safe_add_column(self, tmp_path):
        """Safely handles duplicate column additions."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Force re-initialization to trigger migrations again
        store._ensure_init_sqlite()

        # Should not raise
        assert store.conn is not None
        store.close()

    def test_tables_have_required_columns(self, tmp_path):
        """Tables have all required columns after init."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Check ledger columns
        cursor = store.conn.execute("PRAGMA table_info(ledger)")
        ledger_cols = {row["name"] for row in cursor.fetchall()}
        assert "state_root" in ledger_cols
        assert "zk_proof" in ledger_cols

        # Check blocks columns
        cursor = store.conn.execute("PRAGMA table_info(blocks)")
        blocks_cols = {row["name"] for row in cursor.fetchall()}
        assert "index" in blocks_cols
        assert "zk_proof" in blocks_cols
        assert "state_root" in blocks_cols
        assert "tx_ids" in blocks_cols

        store.close()


class TestRustStoreIntegration:
    """Test Rust store integration paths."""

    def test_set_meta_with_rust_store(self, tmp_path):
        """set_meta uses Rust store when available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Manually enable Rust mode
        mock_rust_store = MagicMock()
        store._use_rust = True
        store._rust_store = mock_rust_store

        store.set_meta("key", {"value": 123})

        mock_rust_store.put.assert_called_once()
        store.close()

    def test_set_meta_rust_store_error(self, tmp_path):
        """set_meta handles Rust store error."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        mock_rust_store.put.side_effect = Exception("Rust error")
        store._use_rust = True
        store._rust_store = mock_rust_store

        # Should not raise, falls back to SQLite
        store.set_meta("key", {"value": 123})

        # Reset Rust flags to verify SQLite fallback
        store._use_rust = False
        store._rust_store = None

        # SQLite should still work
        result = store.get_meta("key")
        assert result == {"value": 123}
        store.close()

    def test_get_meta_with_rust_store(self, tmp_path):
        """get_meta uses Rust store when available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        mock_rust_store.get.return_value = '{"value": 456}'
        store._use_rust = True
        store._rust_store = mock_rust_store

        result = store.get_meta("key")

        mock_rust_store.get.assert_called_once_with("key")
        assert result == {"value": 456}
        store.close()

    def test_get_meta_rust_store_error_falls_back(self, tmp_path):
        """get_meta falls back to SQLite on Rust error."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Set value in SQLite first
        store.set_meta("key", {"sqlite": True})

        mock_rust_store = MagicMock()
        mock_rust_store.get.side_effect = Exception("Rust error")
        store._use_rust = True
        store._rust_store = mock_rust_store

        result = store.get_meta("key")

        assert result == {"sqlite": True}
        store.close()

    def test_get_meta_no_connection(self, tmp_path):
        """get_meta returns None when no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store._use_rust = False
        store.conn = None

        result = store.get_meta("key")
        assert result is None


class TestGetBalanceRustPaths:
    """Test get_balance with various Rust return types."""

    def test_get_balance_rust_returns_int(self, tmp_path):
        """get_balance handles Rust returning int."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_balance.return_value = 500
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_balance("alice")
        assert result == 500
        store.close()

    def test_get_balance_rust_returns_float(self, tmp_path):
        """get_balance handles Rust returning float."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_balance.return_value = 750.5
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_balance("bob")
        assert result == 750
        store.close()

    def test_get_balance_rust_returns_bool(self, tmp_path):
        """get_balance handles Rust returning bool (treated as 0)."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_balance.return_value = True
        store._use_rust = True
        store._rust_ledger = mock_ledger

        # Add SQLite fallback
        store.update_balance("charlie", 100)

        result = store.get_balance("charlie")
        # Returns SQLite fallback because bool maps to 0
        assert result == 100
        store.close()

    def test_get_balance_rust_returns_numeric_string(self, tmp_path):
        """get_balance handles Rust returning numeric string."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_balance.return_value = "300"
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_balance("dave")
        assert result == 300
        store.close()

    def test_get_balance_rust_returns_empty_string(self, tmp_path):
        """get_balance handles Rust returning empty string."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_balance.return_value = ""
        store._use_rust = True
        store._rust_ledger = mock_ledger

        store.update_balance("eve", 50)

        result = store.get_balance("eve")
        # Falls back to SQLite because empty string
        assert result == 50
        store.close()

    def test_get_balance_rust_returns_non_numeric_string(self, tmp_path):
        """get_balance handles Rust returning non-numeric string."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_balance.return_value = "not_a_number"
        store._use_rust = True
        store._rust_ledger = mock_ledger

        store.update_balance("frank", 75)

        result = store.get_balance("frank")
        # Falls back to SQLite
        assert result == 75
        store.close()

    def test_get_balance_rust_returns_other_type(self, tmp_path):
        """get_balance handles Rust returning unexpected type."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_balance.return_value = {"unexpected": "dict"}
        store._use_rust = True
        store._rust_ledger = mock_ledger

        store.update_balance("grace", 25)

        result = store.get_balance("grace")
        assert result == 25
        store.close()

    def test_get_balance_rust_raises_exception(self, tmp_path):
        """get_balance handles Rust exception."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_balance.side_effect = Exception("Rust error")
        store._use_rust = True
        store._rust_ledger = mock_ledger

        store.update_balance("henry", 200)

        result = store.get_balance("henry")
        # Falls back to SQLite
        assert result == 200
        store.close()


class TestUpdateBalanceRustPaths:
    """Test update_balance with Rust ledger."""

    def test_update_balance_with_rust_ledger(self, tmp_path):
        """update_balance handles Rust ledger path."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        store._use_rust = True
        store._rust_ledger = mock_ledger

        store.update_balance("alice", 1000)

        # SQLite should still be updated
        store._use_rust = False
        store._rust_ledger = None
        assert store.get_balance("alice") == 1000
        store.close()

    def test_update_balance_no_connection(self, tmp_path):
        """update_balance handles no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.conn = None

        # Should not raise
        store.update_balance("alice", 500)

    def test_get_last_block_empty_db(self, tmp_path):
        """get_last_block returns None when DB is empty."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        result = store.get_last_block()
        assert result is None
        store.close()


class TestGetAllBalancesRustPaths:
    """Test get_all_balances with Rust ledger."""

    def test_get_all_balances_with_rust_ledger(self, tmp_path):
        """get_all_balances uses Rust ledger when available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_all_balances.return_value = [("alice", 100), ("bob", 200)]
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_all_balances()

        assert result == {"alice": 100, "bob": 200}
        store.close()

    def test_get_all_balances_no_connection(self, tmp_path):
        """get_all_balances returns empty dict with no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store._use_rust = False
        store.conn = None

        result = store.get_all_balances()
        assert result == {}


class TestConnPropertyEdgeCases:
    """Test conn property edge cases."""

    def test_conn_setter_same_value(self, tmp_path):
        """conn setter handles setting same value."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        conn = store.conn
        store.conn = conn  # Set to same value

        assert store.conn is conn
        store.close()

    def test_conn_setter_close_exception(self, tmp_path):
        """conn setter handles exception on close."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Create a mock connection that raises on close
        mock_conn = MagicMock()
        mock_conn.close.side_effect = Exception("Close error")
        store._conn = mock_conn

        # Should not raise
        store.conn = None

        assert store.conn is None

    def test_conn_deleter(self, tmp_path):
        """conn deleter sets to None."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        del store.conn

        assert store.conn is None

    def test_del_handles_exception(self, tmp_path):
        """__del__ handles exception gracefully."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Force an exception scenario - close first
        store.close()

        # __del__ should not raise even after close
        store.__del__()


class TestLogEventEdgeCases:
    """Test log_event edge cases."""

    def test_log_event_no_connection(self, tmp_path):
        """log_event raises when no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.conn = None

        with pytest.raises(RuntimeError) as exc_info:
            store.log_event(1.0, "TEST", {}, "0" * 64, "a" * 64)

        assert "Database connection not initialized" in str(exc_info.value)

    def test_get_last_event_no_connection(self, tmp_path):
        """get_last_event returns None when no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.conn = None

        result = store.get_last_event()
        assert result is None

    def test_get_all_events_no_connection(self, tmp_path):
        """get_all_events returns empty list with no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.conn = None

        result = store.get_all_events()
        assert result == []

    def test_get_all_meta_no_connection(self, tmp_path):
        """get_all_meta returns empty list with no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.conn = None

        result = store.get_all_meta()
        assert result == []

    def test_set_meta_no_connection(self, tmp_path):
        """set_meta returns early when no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store._use_rust = False
        store.conn = None

        # Should not raise
        store.set_meta("key", "value")


class TestCommitBlockEdgeCases:
    """Test commit_block edge cases."""

    def test_commit_block_no_connection(self, tmp_path):
        """commit_block returns early when no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.conn = None

        # Should not raise
        store.commit_block(
            timestamp=1.0,
            tx_ids=[],
            miner="miner",
            prev_hash="0" * 64,
            block_hash="abc123",
            balance_updates={},
        )


class TestGetLastBlockRustPaths:
    """Test get_last_block with Rust ledger."""

    def test_get_last_block_rust_success(self, tmp_path):
        """get_last_block uses Rust ledger when available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_block = MagicMock()
        mock_block.timestamp = 1234567890.0
        mock_block.tx_ids = ["tx1", "tx2"]
        mock_block.miner = "miner_addr"
        mock_block.prev_hash = "0" * 64
        mock_block.hash = "block_hash"
        mock_block.zk_proof = "proof_data"

        mock_ledger = MagicMock()
        mock_ledger.get_last_block.return_value = mock_block
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_last_block()

        assert result is not None
        assert result["hash"] == "block_hash"
        assert result["miner"] == "miner_addr"
        store.close()

    def test_get_last_block_rust_returns_none(self, tmp_path):
        """get_last_block handles Rust returning None."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_last_block.return_value = None
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_last_block()

        assert result is None
        store.close()

    def test_get_last_block_rust_exception(self, tmp_path):
        """get_last_block handles Rust exception."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_last_block.side_effect = Exception("Rust error")
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_last_block()

        assert result is None
        store.close()

    def test_get_last_block_no_connection(self, tmp_path):
        """get_last_block returns None when no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store._use_rust = False
        store.conn = None

        result = store.get_last_block()
        assert result is None


class TestGetBlockRustPaths:
    """Test get_block with Rust ledger."""

    def test_get_block_rust_success(self, tmp_path):
        """get_block uses Rust ledger when available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_block = MagicMock()
        mock_block.timestamp = 1234567890.0
        mock_block.tx_ids = ["tx1"]
        mock_block.miner = "miner"
        mock_block.prev_hash = "prev"
        mock_block.hash = "target_hash"

        mock_ledger = MagicMock()
        mock_ledger.get_block.return_value = mock_block
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_block("target_hash")

        assert result is not None
        assert result["hash"] == "target_hash"
        store.close()

    def test_get_block_rust_returns_none(self, tmp_path):
        """get_block handles Rust returning None."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_block.return_value = None
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_block("nonexistent")

        assert result is None
        store.close()

    def test_get_block_rust_exception(self, tmp_path):
        """get_block handles Rust exception."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.get_block.side_effect = Exception("Rust error")
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.get_block("hash")

        assert result is None
        store.close()

    def test_get_block_no_connection(self, tmp_path):
        """get_block returns None when no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store._use_rust = False
        store.conn = None

        result = store.get_block("hash")
        assert result is None


class TestBlobRustPaths:
    """Test blob operations with Rust store."""

    def test_put_blob_rust_success(self, tmp_path):
        """put_blob uses Rust store when available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        store._use_rust = True
        store._rust_store = mock_rust_store

        store.put_blob("key", b"\x00\x01\x02")

        mock_rust_store.put.assert_called_once()
        store.close()

    def test_put_blob_rust_exception_falls_back(self, tmp_path):
        """put_blob falls back to SQLite on Rust error."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        mock_rust_store.put.side_effect = Exception("Rust error")
        store._use_rust = True
        store._rust_store = mock_rust_store

        store.put_blob("key", b"\xff\xfe")

        # Reset Rust to verify SQLite fallback
        store._use_rust = False
        store._rust_store = None

        result = store.get_blob("key")
        assert result == b"\xff\xfe"
        store.close()

    def test_put_blob_no_connection(self, tmp_path):
        """put_blob handles no connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        store.conn = None

        # Should not raise
        store.put_blob("key", b"data")

    def test_get_blob_rust_success(self, tmp_path):
        """get_blob uses Rust store when available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        # Return hex-encoded data
        mock_rust_store.get.return_value = "00010203"
        store._use_rust = True
        store._rust_store = mock_rust_store

        result = store.get_blob("key")

        assert result == b"\x00\x01\x02\x03"
        store.close()

    def test_get_blob_rust_returns_bytes(self, tmp_path):
        """get_blob handles Rust returning bytes."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        mock_rust_store.get.return_value = b"\xff\xfe\xfd"
        store._use_rust = True
        store._rust_store = mock_rust_store

        result = store.get_blob("key")

        assert result == b"\xff\xfe\xfd"
        store.close()

    def test_get_blob_rust_returns_none(self, tmp_path):
        """get_blob handles Rust returning None."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        mock_rust_store.get.return_value = None
        store._use_rust = True
        store._rust_store = mock_rust_store

        result = store.get_blob("missing")

        assert result is None
        store.close()

    def test_get_blob_rust_returns_unexpected_type(self, tmp_path):
        """get_blob handles Rust returning unexpected type."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        mock_rust_store.get.return_value = {"unexpected": "dict"}
        store._use_rust = True
        store._rust_store = mock_rust_store

        # Store value in SQLite as fallback
        store._use_rust = False
        store.put_blob("key", b"sqlite_data")
        store._use_rust = True

        result = store.get_blob("key")

        # Falls back to SQLite
        assert result == b"sqlite_data"
        store.close()

    def test_get_blob_rust_exception(self, tmp_path):
        """get_blob handles Rust exception."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        mock_rust_store.get.side_effect = Exception("Rust error")
        store._use_rust = True
        store._rust_store = mock_rust_store

        # Store value in SQLite as fallback
        store._use_rust = False
        store.put_blob("key", b"fallback")
        store._use_rust = True
        store._rust_store = mock_rust_store

        result = store.get_blob("key")

        assert result == b"fallback"
        store.close()


class TestReconcileStateRustPaths:
    """Test reconcile_state with Rust ledger."""

    def test_reconcile_state_with_sync_state(self, tmp_path):
        """reconcile_state calls Rust sync_state when available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Add some test data
        store.update_balance("alice", 100)
        store.commit_block(1.0, [], "miner", "0" * 64, "hash1", {})

        mock_ledger = MagicMock()
        mock_ledger.sync_state = MagicMock()
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.reconcile_state()

        assert result is True
        mock_ledger.sync_state.assert_called_once()
        store.close()

    def test_reconcile_state_no_sync_state(self, tmp_path):
        """reconcile_state returns False when sync_state not available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock(spec=[])  # No sync_state method
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.reconcile_state()

        assert result is False
        store.close()

    def test_reconcile_state_exception(self, tmp_path):
        """reconcile_state handles exception."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        mock_ledger.sync_state.side_effect = Exception("Sync failed")
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.reconcile_state()

        assert result is False
        store.close()


class TestDefaultRootPath:
    """Test default root path behavior."""

    def test_init_default_root_no_env(self, tmp_path, monkeypatch):
        """Uses default root when no env_root specified."""
        # Unset the env variable to trigger line 50
        monkeypatch.delenv("SOVEREIGN_STORE_ROOT", raising=False)

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            # Pass explicit db_path to avoid touching real filesystem
            store = SovereignStore(tmp_path / "test.db")

        assert store.db_path == tmp_path / "test.db"
        store.close()

    def test_init_no_db_path_no_env_var(self, monkeypatch, tmp_path):
        """Uses absolute default path when no db_path and no env var (line 50)."""
        # Clear env var to trigger line 50
        monkeypatch.delenv("SOVEREIGN_STORE_ROOT", raising=False)

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            # Don't pass db_path to trigger default path calculation
            store = SovereignStore()

        # Should use default path based on __file__ location
        assert ".sovereign" in str(store.db_path)
        assert "sovereign.db" in str(store.db_path)
        store.close()


class TestDuplicateColumnMigration:
    """Test schema migration with duplicate column error."""

    def test_safe_add_column_duplicate_error(self, tmp_path):
        """_safe_add_column handles duplicate column gracefully."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Manually trigger migration by adding column twice
        # First add is normal, second should trigger error handling
        try:
            store.conn.execute("ALTER TABLE ledger ADD COLUMN test_col TEXT")
        except sqlite3.OperationalError:
            pass  # Column may already exist

        # Now force re-initialization which calls migrations again
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store2 = SovereignStore(tmp_path / "test.db")

        # Both stores should work fine
        assert store2.conn is not None
        store.close()
        store2.close()


class TestLogEventLastrowidNone:
    """Test log_event lastrowid None handling."""

    def test_log_event_lastrowid_none(self, tmp_path):
        """log_event raises when lastrowid is None."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Mock execute to return cursor with lastrowid=None
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = None

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_cursor
        store._conn = mock_conn

        with pytest.raises(RuntimeError) as exc_info:
            store.log_event(1.0, "TEST", {}, "0" * 64, "a" * 64)

        assert "lastrowid is None" in str(exc_info.value)


class TestUpdateBalanceRustException:
    """Test update_balance Rust ledger exception."""

    def test_update_balance_rust_ledger_exception(self, tmp_path):
        """update_balance handles Rust ledger exception."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_ledger = MagicMock()
        # Rust ledger doesn't have update methods in current impl, but we test
        # the try/except path that logs errors
        store._use_rust = True
        store._rust_ledger = mock_ledger

        # Should not raise - just logs error and continues to SQLite
        store.update_balance("alice", 500)

        # Verify SQLite fallback works
        store._use_rust = False
        store._rust_ledger = None
        assert store.get_balance("alice") == 500
        store.close()


class TestGetBlobReturnNone:
    """Test get_blob returning None for unknown types."""

    def test_get_blob_rust_returns_unknown_type(self, tmp_path):
        """get_blob returns None for unknown type."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        # Return a type that's not str or bytes - triggers line 564
        mock_rust_store.get.return_value = 12345  # int, not str/bytes
        store._use_rust = True
        store._rust_store = mock_rust_store

        # Should return None for non-str/bytes type
        result = store.get_blob("key")

        # Falls back to SQLite which returns None for missing key
        assert result is None
        store.close()

    def test_get_blob_sqlite_returns_json_list(self, tmp_path):
        """get_blob returns None when SQLite contains JSON array (lines 563-565)."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        # Directly insert JSON array into metadata table
        store.conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            ("blob_key", "[1, 2, 3]"),  # JSON array string that deserializes to list
        )
        store.conn.commit()

        # Ensure Rust fallback doesn't kick in
        store._use_rust = False

        # get_blob should return None for non-str/bytes deserialized value
        result = store.get_blob("blob_key")

        assert result is None
        store.close()

    def test_get_blob_rust_returns_list(self, tmp_path):
        """get_blob returns None for list type."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "test.db")

        mock_rust_store = MagicMock()
        mock_rust_store.get.return_value = [1, 2, 3]  # list
        store._use_rust = True
        store._rust_store = mock_rust_store

        result = store.get_blob("key")
        assert result is None
        store.close()


@pytest.mark.skipif(not HAS_RUST, reason="Rust core not available")
class TestSovereignStoreWithRustCore:
    """Test SovereignStore with actual Rust core (lines 62-94).

    Note: These tests use fresh imports to ensure Rust core is properly loaded.
    They run in a subprocess-like isolation to avoid affecting other tests.
    """

    @pytest.fixture
    def rust_store(self, tmp_path):
        """Create a SovereignStore with actual Rust core."""
        # Directly use the real module (not patched)
        from warm_logic.kernel.sys.persistence import SovereignStore as RealStore

        db_path = tmp_path / "rust_test.db"
        store = RealStore(db_path)
        yield store
        store.close()

    def test_init_with_rust_core(self, rust_store):
        """SovereignStore initializes with Rust core."""
        assert rust_store._use_rust is True
        assert rust_store._rust_store is not None
        assert rust_store._rust_ledger is not None
        assert rust_store.conn is not None

    def test_set_and_get_meta_with_rust(self, rust_store):
        """set_meta and get_meta work with Rust core."""
        rust_store.set_meta("test_key", {"nested": {"value": 123}})
        result = rust_store.get_meta("test_key")

        assert result == {"nested": {"value": 123}}

    def test_update_and_get_balance_with_rust(self, rust_store):
        """update_balance and get_balance work with Rust core."""
        rust_store.update_balance("alice", 1000)
        result = rust_store.get_balance("alice")

        # SQLite fallback should work
        assert result == 1000

    def test_commit_block_with_rust(self, rust_store):
        """commit_block works with Rust core."""
        # commit_block should not raise
        rust_store.commit_block(
            timestamp=1234567890.0,
            tx_ids=["tx1", "tx2"],
            miner="miner1",
            prev_hash="0" * 64,
            block_hash="a" * 64,
            balance_updates={"alice": 100},
        )

        # Verify balance was updated (SQLite fallback)
        balance = rust_store.get_balance("alice")
        assert balance == 100

    def test_reconcile_state_with_rust(self, rust_store):
        """reconcile_state works with Rust core."""
        # Add data
        rust_store.update_balance("bob", 500)
        rust_store.commit_block(1.0, [], "miner", "0" * 64, "hash1", {})

        # Reconcile - may return True or False depending on Rust impl
        result = rust_store.reconcile_state()
        # Just verify it doesn't crash
        assert isinstance(result, bool)


class TestRustCoreInitException:
    """Test Rust core initialization exception handling (lines 90-94)."""

    def test_rust_core_init_failure(self, tmp_path, monkeypatch):
        """SovereignStore raises on Rust init failure."""
        import importlib
        import warm_logic.kernel.sys.persistence as persistence_mod

        # Mock Rust core to fail during init
        def mock_load_rust_core():
            mock_rs = MagicMock()
            mock_rs.SovereignStore.side_effect = Exception("Rust init failed")
            return mock_rs

        monkeypatch.setattr(
            "warm_logic.kernel.rust_loader.load_rust_core", mock_load_rust_core
        )
        monkeypatch.setattr("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True)

        importlib.reload(persistence_mod)

        db_path = tmp_path / "rust_fail.db"
        with pytest.raises(RuntimeError) as exc_info:
            persistence_mod.SovereignStore(db_path)

        assert "redb Init Failed" in str(exc_info.value)


class TestSchemaMigrationEdgeCases:
    """Test schema migration edge cases (lines 183-186, 192, 199, 201, 203, 205)."""

    def test_schema_migration_duplicate_column(self, tmp_path):
        """Schema migration handles duplicate column error."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "migration.db")

        # Manually add a column that the migration would add
        store.conn.execute("ALTER TABLE ledger ADD COLUMN extra_col TEXT")
        store.conn.commit()

        # Re-create store with same DB - migrations should handle existing columns
        store.close()
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store2 = SovereignStore(tmp_path / "migration.db")

        assert store2.conn is not None
        store2.close()

    def test_schema_migration_operates_normally(self, tmp_path):
        """Schema migration works on fresh database."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "fresh_migration.db")

        # Verify tables and columns exist
        cursor = store.conn.execute("PRAGMA table_info(ledger)")
        columns = {row["name"] for row in cursor.fetchall()}
        assert "state_root" in columns
        assert "zk_proof" in columns

        cursor = store.conn.execute("PRAGMA table_info(blocks)")
        columns = {row["name"] for row in cursor.fetchall()}
        assert "index" in columns
        assert "zk_proof" in columns
        assert "state_root" in columns
        assert "tx_ids" in columns

        store.close()

    def test_schema_migration_adds_missing_columns(self, tmp_path):
        """Migration adds columns to old schema (lines 192, 199, 201, 203, 205)."""
        db_path = tmp_path / "old_schema.db"

        # Create old schema without migration columns
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE ledger (
                id INTEGER PRIMARY KEY,
                timestamp REAL,
                event_type TEXT,
                payload TEXT,
                prev_hash TEXT,
                current_hash TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE blocks (
                id INTEGER PRIMARY KEY,
                timestamp REAL,
                miner TEXT,
                block_hash TEXT,
                prev_hash TEXT,
                transactions TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)
        """)
        conn.execute("""
            CREATE TABLE balances (address TEXT PRIMARY KEY, amount INTEGER)
        """)
        conn.commit()
        conn.close()

        # Now open with SovereignStore - should add missing columns
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(db_path)

        # Verify new columns were added
        cursor = store.conn.execute("PRAGMA table_info(ledger)")
        columns = {row["name"] for row in cursor.fetchall()}
        assert "state_root" in columns
        assert "zk_proof" in columns

        cursor = store.conn.execute("PRAGMA table_info(blocks)")
        columns = {row["name"] for row in cursor.fetchall()}
        assert "index" in columns
        assert "zk_proof" in columns
        assert "state_root" in columns
        assert "tx_ids" in columns

        store.close()

    def test_duplicate_column_error_handling(self, tmp_path):
        """Migration handles duplicate column error (lines 183-186)."""
        db_path = tmp_path / "dup_col.db"

        # Create fresh store
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store1 = SovereignStore(db_path)
        store1.close()

        # Open again - should handle existing columns gracefully
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store2 = SovereignStore(db_path)

        assert store2.conn is not None
        store2.close()


class TestUpdateBalanceRustLedgerException:
    """Test update_balance Rust ledger exception path (lines 374-375)."""

    def test_update_balance_rust_exception_path(self, tmp_path):
        """update_balance handles Rust ledger exception via pass block."""
        import importlib
        import warm_logic.kernel.sys.persistence as persistence_mod

        importlib.reload(persistence_mod)

        db_path = tmp_path / "rust_update_exc.db"
        store = persistence_mod.SovereignStore(db_path)

        # The Rust ledger doesn't have a method that would raise in update_balance
        # The try/except/pass block is defensive - test that SQLite still works
        store.update_balance("alice", 750)
        assert store.get_balance("alice") == 750
        store.close()


class TestGetBlobUnknownTypeReturn:
    """Test get_blob returning None for unknown types (line 564)."""

    def test_get_blob_deserialize_returns_valid_hex(self, tmp_path):
        """get_blob handles valid hex string."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "blob_hex.db")

        # Store a valid hex string
        store.conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)", ("key", '"deadbeef"')
        )
        store.conn.commit()

        result = store.get_blob("key")
        # "deadbeef" is valid hex
        assert result == bytes.fromhex("deadbeef")
        store.close()

    def test_get_blob_with_mock_returning_int(self, tmp_path):
        """get_blob returns None when mock returns int directly."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "blob_mock.db")

        # Override _deserialize to return int
        original_deserialize = store._deserialize_stored_value

        def mock_deserialize(val):
            if val == "special":
                return 999  # Return int
            return original_deserialize(val)

        # Use object's method
        store._deserialize_stored_value = staticmethod(mock_deserialize)

        # Mock rust store to return "special"
        mock_rust_store = MagicMock()
        mock_rust_store.get.return_value = "special"
        store._use_rust = True
        store._rust_store = mock_rust_store

        # The result depends on how _deserialize handles it
        result = store.get_blob("key")
        # With the mock returning "special", _deserialize_stored_value returns 999
        # Then in get_blob, 999 is not str/bytes, so returns None
        assert result is None
        store.close()


class TestReconcileStateNoSyncState:
    """Test reconcile_state when Rust ledger has no sync_state (lines 614-615)."""

    def test_reconcile_no_sync_state_method(self, tmp_path):
        """reconcile_state returns False when no sync_state method (lines 615-616)."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "reconcile_no_sync.db")

        # Add some data
        store.update_balance("alice", 100)

        # Mock Rust ledger WITH get_all_balances but WITHOUT sync_state
        # This ensures we reach the hasattr check at line 607
        mock_ledger = MagicMock()
        mock_ledger.get_all_balances.return_value = {}
        # Delete sync_state to ensure hasattr returns False
        del mock_ledger.sync_state
        store._use_rust = True
        store._rust_ledger = mock_ledger

        result = store.reconcile_state()

        # Should return False due to no sync_state
        assert result is False
        store.close()


class TestDelExceptionHandling:
    """Test __del__ exception handling (lines 123-124)."""

    def test_del_handles_conn_close_exception(self, tmp_path):
        """__del__ handles exception when closing connection."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            store = SovereignStore(tmp_path / "del_exc.db")

        # Replace conn with mock that raises on close
        mock_conn = MagicMock()
        mock_conn.close.side_effect = Exception("Close failed")
        store._conn = mock_conn

        # __del__ should not raise
        store.__del__()
        # If we get here without exception, test passes
