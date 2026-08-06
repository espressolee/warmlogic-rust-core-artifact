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

from warm_logic.kernel.ops.invariants import (
    FailLatch,
    InvariantManager,
    JSeriesValidator,
    KSeriesValidator,
    LSeriesValidator,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestInvariantsCoverage(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        FailLatch._instance = None
        # Use a fresh manager with MLDSA mocked
        with mock.patch("warm_logic.kernel.ops.invariants.MLDSA"):
            self.manager = InvariantManager()

    def test_fail_latch_singleton(self):
        l1 = FailLatch()
        l2 = FailLatch()
        self.assertIs(l1, l2)
        l1.trigger("Test")
        self.assertTrue(l2.latched)

    def test_j_series_validation(self):
        with mock.patch("warm_logic.kernel.ops.invariants.MLDSA") as mock_mldsa_cls:
            val = JSeriesValidator()
            mock_mldsa = mock_mldsa_cls.return_value
            self.assertFalse(val.validate("h", {}))
            mock_mldsa.verify.return_value = True
            self.assertTrue(val.validate("h", {"signature": "s", "pub_key": "p"}))

    def test_k_series_validation(self):
        val = KSeriesValidator()
        with mock.patch("warm_logic.kernel.ops.invariants.time.time") as mock_t:
            # 1. Init
            mock_t.return_value = 1000.0
            self.assertTrue(val.validate())

            # 2. Regular (Pass, 50ms drift)
            mock_t.return_value = 1000.05
            self.assertTrue(val.validate())

            # 3. Fail (Now strict 100ms, no grace)
            mock_t.return_value = 1000.20  # 150ms drift
            with self.assertLogs("InvariantGuard", level="CRITICAL"):
                self.assertFalse(val.validate())

    def test_l_series_validation(self):
        val = LSeriesValidator()
        self.assertTrue(val.validate(0))
        self.assertTrue(val.validate(1))
        self.assertFalse(val.validate(1))
        self.assertFalse(val.validate(0))

    def test_manager_workflow(self):
        with mock.patch.object(self.manager.j_val, "validate", return_value=True):
            with mock.patch.object(self.manager.k_val, "validate", return_value=True):
                self.assertTrue(self.manager.check_all(0, "h", {}))

    def test_persistent_latch(self):
        # 1. Baseline
        self.assertTrue(self.manager.l_val.validate(0))

        # 2. Trigger via Logic
        self.assertFalse(self.manager.l_val.validate(0))  # Violation

        # 3. Manager check should trigger latch
        self.assertFalse(self.manager.check_all(0, "h", {}))
        self.assertTrue(FailLatch().latched)

        # 4. Subsequent calls must fail even if logic is correct

    def test_manager_triggers(self):
        # 1. K-Series Trigger
        with mock.patch.object(self.manager.k_val, "validate", return_value=False):
            with self.assertLogs("InvariantGuard", level="CRITICAL") as cm:
                self.assertFalse(self.manager.check_all(10, "h", {}))
                self.assertIn("K-Series Violation", cm.output[0])

        # This call should hit the early return at line 121
        self.assertFalse(self.manager.check_all(11, "h", {}))

        # Reset singleton AND manager reference
        FailLatch._instance = None
        with mock.patch("warm_logic.kernel.ops.invariants.MLDSA"):
            self.manager = InvariantManager()

        # 2. J-Series Trigger
        with mock.patch.object(self.manager.k_val, "validate", return_value=True):
            with mock.patch.object(self.manager.j_val, "validate", return_value=False):
                with self.assertLogs("InvariantGuard", level="CRITICAL") as cm:
                    self.assertFalse(self.manager.check_all(10, "h", {}))
                    self.assertIn("J-Series Violation", cm.output[0])
