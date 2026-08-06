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


from warm_logic.kernel.constitution import ConstitutionalGuard
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestConstitutionCoverage(WarmLogicTestCase):
    def test_load_constitution_missing(self):
        with mock.patch(
            "warm_logic.kernel.constitution.Path.exists", return_value=False
        ):
            guard = ConstitutionalGuard()
            self.assertIsNone(guard.constitution)

    def test_load_constitution_corrupt(self):
        with mock.patch(
            "warm_logic.kernel.constitution.Path.exists", return_value=True
        ):
            with mock.patch(
                "builtins.open", mock.mock_open(read_data="corrupt: {yaml")
            ):
                guard = ConstitutionalGuard()
                self.assertIsNone(guard.constitution)

    def test_verify_failure(self):
        with mock.patch(
            "warm_logic.kernel.constitution.Path.exists", side_effect=[True, False]
        ):
            with mock.patch(
                "builtins.open", mock.mock_open(read_data="data: {}\nsignature: '123'")
            ):
                guard = ConstitutionalGuard()
                self.assertIsNone(guard.constitution)

    def test_verify_exception(self):
        with mock.patch(
            "warm_logic.kernel.constitution.Path.exists", return_value=True
        ):
            with mock.patch(
                "builtins.open", mock.mock_open(read_data="data: {}\nsignature: '123'")
            ):
                with mock.patch(
                    "warm_logic.kernel.constitution.Path.read_bytes",
                    side_effect=Exception("Read Fail"),
                ):
                    guard = ConstitutionalGuard()
                    self.assertIsNone(guard.constitution)

    def test_sanitize_logic(self):
        with mock.patch(
            "warm_logic.kernel.constitution.Path.exists", return_value=False
        ):
            guard = ConstitutionalGuard()

        guard.constitution = {
            "sensitive_keywords": ["SECRET", "INTERNAL"],
            "entropy_threshold": 3.0,
            "defense_level": 100,
        }

        # 1. Redaction + Entropy Block (level 100)
        # Total violations = 2 (keywords) + 1 (entropy block) = 3
        text = "This is a SECRET INTERNAL document."
        safe, count = guard.sanitize(text)
        self.assertEqual(count, 3)

        # 2. Defense level fallback (< 50)
        guard.constitution["defense_level"] = 10
        # Entropy violation doesn't increment count or block if level <= 50
        text_plain = "Simple phrase"
        guard.constitution["entropy_threshold"] = 1.0  # Force violation
        safe_low, count_low = guard.sanitize(text_plain)
        self.assertEqual(count_low, 0)
        self.assertEqual(safe_low, text_plain)

    def test_calculate_entropy_edge(self):
        with mock.patch(
            "warm_logic.kernel.constitution.Path.exists", return_value=False
        ):
            guard = ConstitutionalGuard()
        self.assertEqual(guard.calculate_entropy(""), 0)
        self.assertEqual(guard.calculate_entropy(None), 0)

    def test_module_entry_point(self):
        from warm_logic.kernel.constitution import constitutional_audit

        with mock.patch(
            "warm_logic.kernel.constitution.guard.sanitize", return_value=("safe", 0)
        ):
            res, count = constitutional_audit("test")
            self.assertEqual(res, "safe")
