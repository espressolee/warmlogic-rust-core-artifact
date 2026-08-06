# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic Sovereign Oracle."""

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.oracle import SovereignOracle


class TestSovereignOracle:
    """Test SovereignOracle data ingestion."""

    def test_init_with_ledger(self):
        """Initializes with ledger reference."""
        mock_ledger = MagicMock()
        oracle = SovereignOracle(mock_ledger)

        assert oracle.ledger is mock_ledger

    def test_ingest_data_success(self):
        """Successfully ingests data and returns hash."""
        mock_store = MagicMock()
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store
        mock_ledger.submit_tx.return_value = True

        oracle = SovereignOracle(mock_ledger)
        result = oracle.ingest_data("weather_api", "temperature", 25.5)

        assert result is not None
        assert len(result) == 64  # SHA3-256 hex
        mock_store.set_meta.assert_called_once()
        mock_ledger.submit_tx.assert_called_once()

    def test_ingest_data_stores_metadata(self):
        """Stores data with correct key format."""
        mock_store = MagicMock()
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store
        mock_ledger.submit_tx.return_value = True

        oracle = SovereignOracle(mock_ledger)
        oracle.ingest_data("sensor_hub", "humidity", 65)

        call_args = mock_store.set_meta.call_args
        key = call_args[0][0]
        value = call_args[0][1]

        assert key == "ORACLE:sensor_hub:humidity"
        assert value["source"] == "sensor_hub"
        assert value["key"] == "humidity"
        assert value["value"] == 65
        assert "ingest_time" in value

    def test_ingest_data_creates_transaction(self):
        """Creates truth transaction with correct format."""
        mock_store = MagicMock()
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store
        mock_ledger.submit_tx.return_value = True

        oracle = SovereignOracle(mock_ledger)
        oracle.ingest_data("market_data", "btc_price", 50000)

        tx = mock_ledger.submit_tx.call_args[0][0]
        assert tx.source.startswith("ORACLE:")
        assert tx.target == "DATA_ROOT"
        assert tx.amount == 0
        assert "SIG_ORACLE_" in tx.signature

    def test_ingest_data_ledger_rejection(self):
        """Returns None when ledger rejects transaction."""
        mock_store = MagicMock()
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store
        mock_ledger.submit_tx.return_value = False

        oracle = SovereignOracle(mock_ledger)
        result = oracle.ingest_data("test", "key", "value")

        assert result is None

    def test_ingest_data_exception(self):
        """Returns None on exception."""
        mock_store = MagicMock()
        mock_store.set_meta.side_effect = Exception("Storage error")
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store

        oracle = SovereignOracle(mock_ledger)
        result = oracle.ingest_data("test", "key", "value")

        assert result is None

    def test_ingest_data_hash_deterministic(self):
        """Same data produces same hash."""
        mock_store = MagicMock()
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store
        mock_ledger.submit_tx.return_value = True

        oracle = SovereignOracle(mock_ledger)

        with patch("warm_logic.kernel.sys.oracle.time") as mock_time:
            mock_time.time.return_value = 1704067200.0

            hash1 = oracle.ingest_data("source", "key", {"nested": True})
            hash2 = oracle.ingest_data("source", "key", {"nested": True})

        assert hash1 == hash2

    def test_verify_data_match(self):
        """Returns True when data matches."""
        mock_store = MagicMock()
        mock_store.get_meta.return_value = {"value": "expected_value"}
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store

        oracle = SovereignOracle(mock_ledger)
        result = oracle.verify_data("source", "key", "expected_value")

        assert result is True
        mock_store.get_meta.assert_called_with("ORACLE:source:key")

    def test_verify_data_mismatch(self):
        """Returns False when data doesn't match."""
        mock_store = MagicMock()
        mock_store.get_meta.return_value = {"value": "actual_value"}
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store

        oracle = SovereignOracle(mock_ledger)
        result = oracle.verify_data("source", "key", "expected_value")

        assert result is False

    def test_verify_data_not_found(self):
        """Returns False when data not in store."""
        mock_store = MagicMock()
        mock_store.get_meta.return_value = None
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store

        oracle = SovereignOracle(mock_ledger)
        result = oracle.verify_data("source", "key", "any_value")

        assert result is False

    def test_verify_data_complex_value(self):
        """Verifies complex nested values."""
        mock_store = MagicMock()
        stored = {"value": {"nested": {"deep": [1, 2, 3]}}}
        mock_store.get_meta.return_value = stored
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store

        oracle = SovereignOracle(mock_ledger)
        result = oracle.verify_data("source", "key", {"nested": {"deep": [1, 2, 3]}})

        assert result is True

    def test_ingest_data_uses_sha3_256(self):
        """Uses SHA3-256 for hashing."""
        mock_store = MagicMock()
        mock_ledger = MagicMock()
        mock_ledger.store = mock_store
        mock_ledger.submit_tx.return_value = True

        oracle = SovereignOracle(mock_ledger)

        with patch("warm_logic.kernel.sys.oracle.time") as mock_time:
            mock_time.time.return_value = 1704067200.0
            result = oracle.ingest_data("src", "key", "val")

        # Manually compute expected hash
        payload = {
            "source": "src",
            "key": "key",
            "value": "val",
            "ingest_time": 1704067200.0,
        }
        payload_json = json.dumps(payload, sort_keys=True)
        expected = hashlib.sha3_256(payload_json.encode()).hexdigest()

        assert result == expected
