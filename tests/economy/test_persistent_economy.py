import os
import shutil
import tempfile
import unittest

from warm_logic.kernel.ops.economy import CreditManager
from warm_logic.kernel.sys.persistence import SovereignStore


class TestPersistentEconomy(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "sovereign.db")
        self.node_id = "node_alpha"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_balance_persistence_across_restarts(self):
        # 1. Start with fresh store
        store1 = SovereignStore(self.db_path)
        economy1 = CreditManager(self.node_id, store=store1, initial_balance=1000.0)

        # Verify initial balance
        self.assertEqual(economy1.get_balance(self.node_id), 1000.0)

        # 2. Deduct some credits
        economy1.deduct(self.node_id, 250.0, "Mutation Tax")
        self.assertEqual(economy1.get_balance(self.node_id), 750.0)

        # 3. Simulate "Restart": Close store and re-open
        store1.close()

        # Ensure it's not just in memory
        store2 = SovereignStore(self.db_path)
        # Re-initialize economy with the same store/node_id
        # initial_balance=1000.0 should NOT overwrite 750.0 in the store
        economy2 = CreditManager(self.node_id, store=store2, initial_balance=1000.0)

        # 4. Final Verification
        self.assertEqual(economy2.get_balance(self.node_id), 750.0)
        print(
            f"✅ [Persistence] Balance verified after restart: {economy2.get_balance(self.node_id)}"
        )

        store2.close()


if __name__ == "__main__":
    unittest.main()
