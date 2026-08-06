from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.oracle import SovereignOracle


class TestOracleSaturation:
    @pytest.fixture
    def mock_ledger(self):
        ledger = MagicMock()
        ledger.store = MagicMock()
        return ledger

    @pytest.fixture
    def oracle(self, mock_ledger):
        return SovereignOracle(ledger=mock_ledger)

    def test_ingest_data_success(self, oracle):
        """Test successful data ingestion and anchoring."""
        oracle.ledger.submit_tx.return_value = True

        tx_hash = oracle.ingest_data("REUTERS", "BTC_PRICE", 50000)

        assert tx_hash is not None
        oracle.ledger.store.set_meta.assert_called()
        oracle.ledger.submit_tx.assert_called()

    def test_ingest_data_rejection(self, oracle):
        """Test ingestion when ledger rejects the transaction."""
        oracle.ledger.submit_tx.return_value = False

        tx_hash = oracle.ingest_data("REUTERS", "BTC_PRICE", 50000)

        assert tx_hash is None
        oracle.ledger.submit_tx.assert_called()

    def test_ingest_data_exception(self, oracle):
        """Test ingestion failure handling (e.g. storage error)."""
        oracle.ledger.store.set_meta.side_effect = Exception("Storage Failure")

        tx_hash = oracle.ingest_data("REUTERS", "BTC_PRICE", 50000)

        assert tx_hash is None

    def test_verify_data_success(self, oracle):
        """Test successful verification."""
        oracle.ledger.store.get_meta.return_value = {"value": 50000}
        assert oracle.verify_data("REUTERS", "BTC_PRICE", 50000) is True

    def test_verify_data_mismatch(self, oracle):
        """Test verification failure on data mismatch."""
        oracle.ledger.store.get_meta.return_value = {"value": 40000}
        assert oracle.verify_data("REUTERS", "BTC_PRICE", 50000) is False

    def test_verify_data_not_found(self, oracle):
        """Test verification failure when data is missing."""
        oracle.ledger.store.get_meta.return_value = None
        assert oracle.verify_data("REUTERS", "BTC_PRICE", 50000) is False
