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
from unittest import mock

from warm_logic.kernel.ops.invariants import FailLatch, InvariantManager
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestInvariantsSurgical(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        FailLatch._instance = None
        with mock.patch("warm_logic.kernel.ops.invariants.MLDSA"):
            self.manager = InvariantManager()

    def test_manager_all_triggers(self):
        # 1. Logic trigger (lines 125-126)
        with mock.patch.object(self.manager.l_val, "validate", return_value=False):
            self.assertFalse(self.manager.check_all(1, "h", {}))
            self.assertTrue(self.manager.latch.latched)
            self.assertIn("L-Series", self.manager.latch.reason)

        # 2. Kinetic trigger (lines 130-131)
        FailLatch._instance.latched = False
        with mock.patch.object(self.manager.l_val, "validate", return_value=True):
            with mock.patch.object(self.manager.k_val, "validate", return_value=False):
                self.assertFalse(self.manager.check_all(1, "h", {}))
                self.assertIn("K-Series", self.manager.latch.reason)

        # 3. Justice trigger (lines 135-136)
        FailLatch._instance.latched = False
        with mock.patch.object(self.manager.l_val, "validate", return_value=True):
            with mock.patch.object(self.manager.k_val, "validate", return_value=True):
                with mock.patch.object(
                    self.manager.j_val, "validate", return_value=False
                ):
                    self.assertFalse(self.manager.check_all(1, "h", {}))
                    self.assertIn("J-Series", self.manager.latch.reason)
