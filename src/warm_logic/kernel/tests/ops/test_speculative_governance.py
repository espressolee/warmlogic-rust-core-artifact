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
import os
import sys
import unittest
from unittest.mock import MagicMock

# Ensure importability
sys.path.append(os.getcwd())

from warm_logic.kernel.ops.governance import QuadraticGovernanceEngine
from warm_logic.kernel.ops.speculative_buffer import speculative_buffer
from warm_logic.kernel.policy import load_guard_thresholds


class TestSpeculativeGovernance(unittest.TestCase):
    def setUp(self):
        self.mock_token_manager = MagicMock()
        self.mock_token_manager.get_balance.return_value = 1000.0
        self.gov_engine = QuadraticGovernanceEngine(
            self.mock_token_manager, node_id="test_node_A"
        )

        # Reset buffer logic for clean slate
        speculative_buffer._buffers = {}
        speculative_buffer.active_layer = None

    def test_vote_logic_branches(self):
        """Cover vote_proposal logic (duplicate checks, for/against)."""
        prop_id = self.gov_engine.submit_proposal("proposer", "ACTION", {})

        # 1. Vote FOR
        success = self.gov_engine.cast_vote("voter_1", prop_id, support=True)
        self.assertTrue(success)
        prop = self.gov_engine.proposals[prop_id]
        self.assertGreater(prop.votes_for, 0)

        # 2. Duplicate Vote (Should Fail)
        success_dup = self.gov_engine.cast_vote("voter_1", prop_id, support=True)
        self.assertFalse(success_dup)

        # 3. Vote AGAINST
        success_against = self.gov_engine.cast_vote("voter_2", prop_id, support=False)
        self.assertTrue(success_against)
        self.assertGreater(prop.votes_against, 0)

    def test_speculative_workflow(self):
        """Original flow ported to unittest."""
        # Baseline
        current_policy = load_guard_thresholds()
        drift_key = "drift_max"

        # Submit
        target_key = "policy:thresholds:drift_max"
        prop_id = self.gov_engine.submit_proposal(
            proposer="test_node_A",
            action="UPDATE_DRIFT_THRESHOLD",
            params={"target_key": target_key, "value": 0.99},
        )

        layer_id = f"pending:{prop_id}"
        self.assertIn(layer_id, speculative_buffer._buffers)

        # Activate Overlay
        speculative_buffer.activate_layer(layer_id)
        spec_policy = load_guard_thresholds()
        self.assertEqual(spec_policy.get(drift_key), 0.99)

        # Reject/Rollback
        self.gov_engine.pipeline.Reject(prop_id)
        speculative_buffer.deactivate_layer()
        self.assertNotIn(layer_id, speculative_buffer._buffers)

        restored = load_guard_thresholds()
        # Should revert to default or original
        self.assertNotEqual(restored.get(drift_key), 0.99)

    def test_tally_unknown_proposal(self):
        res = self.gov_engine.tally_and_execute("unknown_id")
        self.assertFalse(res)


if __name__ == "__main__":
    unittest.main()
