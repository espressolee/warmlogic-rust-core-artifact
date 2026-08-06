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

from warm_logic.kernel.ops.speculative_buffer import SpeculativeManager


class TestSpeculativeSaturation(unittest.TestCase):
    def setUp(self):
        self.mgr = SpeculativeManager()

    def test_layer_lifecycle(self):
        """Line 20-116: full manager coverage."""
        layer_id = "dream1"
        target = "drift_limit"

        # 1. Create and stage
        self.mgr.stage_change(layer_id, "c1", target, 0.5, 0.8, "agent1")
        self.assertIn(layer_id, self.mgr._buffers)
        self.assertEqual(
            self.mgr.get_effective_value(target, 0.5), 0.5
        )  # No overlay active

        # 2. Activate
        self.mgr.activate_layer(layer_id)
        self.assertEqual(self.mgr.get_effective_value(target, 0.5), 0.8)
        self.assertEqual(self.mgr.get_effective_value("other", 10), 10)  # Not in layer

        # 3. Rollback
        self.mgr.rollback_layer(layer_id)
        self.assertIsNone(self.mgr._active_overlay)
        self.assertNotIn(layer_id, self.mgr._buffers)

        # 4. Commit non-existent
        self.assertEqual(self.mgr.commit_layer("ghost"), [])

        # 5. Activate non-existent
        self.mgr.activate_layer("ghost")  # Should log error, not crash
        self.assertIsNone(self.mgr._active_overlay)

    def test_commit_active_overlay(self):
        """Verifies that committing an active overlay resets it."""
        layer_id = "dream2"
        self.mgr.stage_change(layer_id, "c2", "k1", "old", "new", "p")
        self.mgr.activate_layer(layer_id)
        changes = self.mgr.commit_layer(layer_id)
        self.assertEqual(len(changes), 1)
        self.assertIsNone(self.mgr._active_overlay)

    def test_deactivate_layer(self):
        self.mgr.create_layer("L1")
        self.mgr.activate_layer("L1")
        self.mgr.deactivate_layer()
        self.assertIsNone(self.mgr._active_overlay)


if __name__ == "__main__":
    unittest.main()
