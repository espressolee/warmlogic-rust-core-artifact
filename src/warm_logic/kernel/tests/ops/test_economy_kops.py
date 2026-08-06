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
from unittest.mock import MagicMock

from warm_logic.kernel.ops.economy import CreditManager, ResourceAccountant


class TestEconomyWrapper(unittest.TestCase):
    def test_credit_manager_init_no_store(self):
        cm = CreditManager("node_a", initial_balance=500.0)
        self.assertEqual(cm.get_balance("node_a"), 500.0)
        self.assertEqual(cm.get_balance("unknown"), 0.0)

    def test_credit_manager_init_with_store_zero_balance(self):
        mock_store = MagicMock()
        mock_store.get_balance.return_value = 0

        cm = CreditManager("node_a", store=mock_store, initial_balance=1000.0)

        # Verify initial balance injected
        mock_store.update_balance.assert_called_with("node_a", 1000)

    def test_credit_manager_init_with_store_existing_balance(self):
        mock_store = MagicMock()
        mock_store.get_balance.return_value = 500

        cm = CreditManager("node_a", store=mock_store, initial_balance=1000.0)

        # Should NOT update balance if already non-zero
        mock_store.update_balance.assert_not_called()

    def test_transfer_no_store(self):
        cm = CreditManager("node_a", initial_balance=100.0)

        # Success
        success = cm.transfer("node_a", "node_b", 40.0, "payment")
        self.assertTrue(success)
        self.assertEqual(cm.get_balance("node_a"), 60.0)
        self.assertEqual(cm.get_balance("node_b"), 40.0)

        # Fail insufficient funds
        fail = cm.transfer("node_a", "node_b", 100.0, "fail")
        self.assertFalse(fail)
        self.assertEqual(cm.get_balance("node_a"), 60.0)

    def test_transfer_with_store(self):
        mock_store = MagicMock()
        # Mock get_balance to simulate state changes roughly or just return static
        # Since logic calls get_balance multiple times, side_effect is best
        balances = {"node_a": 100, "node_b": 0}

        def get_bal(nid):
            return balances.get(nid, 0)

        def update_bal(nid, val):
            balances[nid] = val

        mock_store.get_balance.side_effect = get_bal
        mock_store.update_balance.side_effect = update_bal

        cm = CreditManager("node_a", store=mock_store)

        success = cm.transfer("node_a", "node_b", 40.0, "store_tx")
        self.assertTrue(success)
        mock_store.update_balance.assert_any_call("node_a", 60)
        mock_store.update_balance.assert_any_call("node_b", 40)

        self.assertEqual(len(cm.transactions), 1)
        self.assertEqual(cm.transactions[0]["reason"], "store_tx")

    def test_deduct_no_store(self):
        cm = CreditManager("node_a", initial_balance=100.0)
        success = cm.deduct("node_a", 10.0, "tax")
        self.assertTrue(success)
        self.assertEqual(cm.get_balance("node_a"), 90.0)

        fail = cm.deduct("node_a", 200.0, "tax_fail")
        self.assertFalse(fail)

    def test_deduct_with_store(self):
        mock_store = MagicMock()
        mock_store.get_balance.return_value = 100

        cm = CreditManager("node_a", store=mock_store)
        cm.deduct("node_a", 10.0, "tax")

        mock_store.update_balance.assert_called_with("node_a", 90)

    def test_resource_accountant(self):
        # Mutation Cost
        cost = ResourceAccountant.calculate_mutation_cost(1024, complexity_score=2.0)
        # Base 50 + (1024/1024)*2 = 52
        self.assertEqual(cost, 52.0)

        # Compute Cost
        # 100ms, load 1.0, unit 0.1 => ()*1*0.1 = 0.1
        cost_compute = ResourceAccountant.calculate_compute_cost(100.0, 1.0)
        self.assertAlmostEqual(cost_compute, 0.1)


if __name__ == "__main__":
    unittest.main()
