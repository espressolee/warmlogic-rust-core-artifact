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
import json
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.ops.audit import SovereignAudit


class TestSovereignAudit(unittest.TestCase):
    def setUp(self):
        # Mock the store and its DB connection
        self.mock_store = MagicMock()
        self.mock_conn = MagicMock()
        self.mock_store.conn = self.mock_conn

        # Initialize audit with mocked store path (it won't be used due to patching)
        pass

    @patch("warm_logic.kernel.ops.audit.SovereignStore")
    def test_audit_clean_infrastructure(self, MockStore):
        """Test a perfect  audit report."""
        # Setup clean chain
        mock_instance = MockStore.return_value
        mock_instance.conn = self.mock_conn
        mock_instance.get_all_balances.return_value = {"ALICE": 100, "BOB": 50}

        # 1. Chain Continuity: Genesis -> Block 1
        # Rows: (hash, prev_hash)
        chain_rows = [
            {"hash": "0" * 63 + "1", "prev_hash": "0" * 64},
            {"hash": "0" * 63 + "2", "prev_hash": "0" * 63 + "1"},
        ]

        # 2. Blocks Data for ZK
        # Rows: (..., zk_proof, txs_data)
        zk_rows = [
            {
                "hash": "0" * 63 + "1",
                "zk_proof": json.dumps(
                    {"prefix": "zkp_v2_bulletproofs", "proof": "p1", "commitment": "c1"}
                ),
                "txs_data": "[]",
            },
            {
                "hash": "0" * 63 + "2",
                "zk_proof": json.dumps(
                    {"prefix": "zkp_v2_bulletproofs", "proof": "p2", "commitment": "c2"}
                ),
                "txs_data": "[]",
            },
        ]

        # Configure cursor responses
        cursor_mock = MagicMock()
        self.mock_conn.execute.return_value = cursor_mock

        def execute_side_effect(query, *args):
            c = MagicMock()
            q = query.strip().upper()

            if "SELECT HASH, PREV_HASH" in q:
                c.fetchall.return_value = chain_rows
            elif "PRAGMA TABLE_INFO" in q:
                # PRAGMA must return tuples for index access row[1]
                c.fetchall.return_value = [(0, "tx_ids", "TEXT", 0, None, 0)]
            elif "SELECT TX_IDS, MINER" in q:
                c.fetchall.return_value = []  # Not deeply used in balance check
            elif "SELECT *, TX_IDS AS TXS_DATA" in q:
                c.fetchall.return_value = zk_rows

            return c

        self.mock_conn.execute.side_effect = execute_side_effect

        with patch(
            "warm_logic.kernel.substrate.proof_zk.ZKProofGenerator.verify_proof",
            return_value=True,
        ):
            audit = SovereignAudit()
            result = audit.run_full_audit()

        self.assertTrue(result)

    @patch("warm_logic.kernel.ops.audit.SovereignStore")
    def test_chain_break_detection(self, MockStore):
        mock_instance = MockStore.return_value
        mock_instance.conn = self.mock_conn

        # Broken chain
        chain_rows = [
            {"hash": "A", "prev_hash": "0" * 64},
            {"hash": "B", "prev_hash": "BAD_HASH"},  # Should be A
        ]

        def execute_side_effect(query, *args):
            c = MagicMock()
            q = query.strip().upper()
            if "SELECT HASH, PREV_HASH" in q:
                c.fetchall.return_value = chain_rows
            elif "PRAGMA" in q:
                c.fetchall.return_value = [(0, "tx_ids", "TEXT", 0, None, 0)]
            elif "SELECT *, TX_IDS" in q:
                # valid proofs to ensure only chain fails
                c.fetchall.return_value = []
            return c

        self.mock_conn.execute.side_effect = execute_side_effect

        # Supply check mock
        mock_instance.get_all_balances.return_value = {"A": 10}

        audit = SovereignAudit()
        result = audit.run_full_audit()
        self.assertFalse(result)

    @patch("warm_logic.kernel.ops.audit.SovereignStore")
    def test_negative_supply_detection(self, MockStore):
        mock_instance = MockStore.return_value
        mock_instance.conn = self.mock_conn

        # Chain valid (empty for simplicity)
        def execute_side_effect(query, *args):
            c = MagicMock()
            q = query.strip().upper()
            if "SELECT HASH, PREV_HASH" in q:
                c.fetchall.return_value = []
            elif "PRAGMA" in q:
                c.fetchall.return_value = [(0, "tx_ids", "TEXT", 0, None, 0)]
            elif "SELECT *, TX_IDS" in q:
                c.fetchall.return_value = []
            return c

        self.mock_conn.execute.side_effect = execute_side_effect

        # Supply check mock
        mock_instance.get_all_balances.return_value = {"ALICE": -100}

        audit = SovereignAudit()
        with patch(
            "warm_logic.kernel.substrate.proof_zk.ZKProofGenerator.verify_proof",
            return_value=True,
        ):
            result = audit.run_full_audit()
        self.assertFalse(result)

    @patch("warm_logic.kernel.ops.audit.SovereignStore")
    def test_malformed_proof_detection(self, MockStore):
        mock_instance = MockStore.return_value
        mock_instance.conn = self.mock_conn
        mock_instance.get_all_balances.return_value = {"A": 10}

        # Chain valid
        chain_rows = [{"hash": "A", "prev_hash": "0" * 64}]

        # Proofs: 1 valid, 1 malformed
        zk_rows = [{"hash": "A", "zk_proof": "NOT_JSON", "txs_data": "[]"}]

        def execute_side_effect(query, *args):
            c = MagicMock()
            q = query.strip().upper()
            if "SELECT HASH, PREV_HASH" in q:
                c.fetchall.return_value = chain_rows
            elif "PRAGMA" in q:
                c.fetchall.return_value = [(0, "tx_ids", "TEXT", 0, None, 0)]
            elif "SELECT *, TX_IDS" in q:
                c.fetchall.return_value = zk_rows
            return c

        self.mock_conn.execute.side_effect = execute_side_effect

        audit = SovereignAudit()
        result = audit.run_full_audit()
        self.assertFalse(result)

    @patch("warm_logic.kernel.ops.audit.SovereignStore")
    def test_missing_proof_detection(self, MockStore):
        mock_instance = MockStore.return_value
        mock_instance.conn = self.mock_conn
        mock_instance.get_all_balances.return_value = {"A": 10}

        zk_rows = [{"hash": "A", "zk_proof": None, "txs_data": "[]"}]

        def execute_side_effect(query, *args):
            c = MagicMock()
            q = query.strip().upper()
            if "SELECT HASH, PREV_HASH" in q:
                c.fetchall.return_value = [{"hash": "A", "prev_hash": "0" * 64}]
            elif "PRAGMA" in q:
                c.fetchall.return_value = [(0, "tx_ids", "TEXT", 0, None, 0)]
            elif "SELECT *, TX_IDS" in q:
                c.fetchall.return_value = zk_rows
            return c

        self.mock_conn.execute.side_effect = execute_side_effect

        audit = SovereignAudit()
        result = audit.run_full_audit()
        self.assertFalse(result)

    @patch("warm_logic.kernel.ops.audit.SovereignStore")
    def test_proof_missing_public_inputs(self, MockStore):
        mock_instance = MockStore.return_value
        mock_instance.conn = self.mock_conn
        mock_instance.get_all_balances.return_value = {"A": 10}

        # Valid JSON but missing public_inputs key
        zk_rows = [
            {"hash": "A", "zk_proof": json.dumps({"foo": "bar"}), "txs_data": "[]"}
        ]

        def execute_side_effect(query, *args):
            c = MagicMock()
            q = query.strip().upper()
            if "SELECT HASH, PREV_HASH" in q:
                c.fetchall.return_value = [{"hash": "A", "prev_hash": "0" * 64}]
            elif "PRAGMA" in q:
                c.fetchall.return_value = [(0, "tx_ids", "TEXT", 0, None, 0)]
            elif "SELECT *, TX_IDS" in q:
                c.fetchall.return_value = zk_rows
            return c

        self.mock_conn.execute.side_effect = execute_side_effect

        audit = SovereignAudit()
        result = audit.run_full_audit()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
