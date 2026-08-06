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

from warm_logic.kernel.sys.cryptography import KineticSovereign
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestCryptographySurgical(WarmLogicTestCase):
    def test_hardware_uuid_failures(self):
        ks = KineticSovereign()

        # 1. Darwin ioreg fail (lines 79-80)
        # Verify fallback or behavior when report is mocked
        mock_report = mock.Mock()
        mock_report.pcr_hash = "TEST-UUID-123"

        with mock.patch("warm_logic.kernel.sys.cryptography.HardwareGuard.get_hardware_report", return_value=mock_report):
             self.assertEqual(ks.get_hardware_uuid(), "TEST-UUID-123")

        # 2. Linux machine-id fail, product_uuid fail (lines 88, 91-93)
        # 2. Linux machine-id fail... actually get_hardware_uuid calls get_hardware_report
        # which is a static method on HardwareGuard.
        # We should just test that it returns the pcr_hash field.
        # The logic about /etc/machine-id is INSIDE HardwareGuard, not here.
        # So this test was testing internal implementation details that have moved.
        # We will update it to verify the pcr_hash propagation.

        mock_report_zero = mock.Mock()
        mock_report_zero.pcr_hash = "00000000-0000-0000-0000-000000000000"

        with mock.patch("warm_logic.kernel.sys.cryptography.HardwareGuard.get_hardware_report", return_value=mock_report_zero):
             self.assertEqual(ks.get_hardware_uuid(), "00000000-0000-0000-0000-000000000000")
