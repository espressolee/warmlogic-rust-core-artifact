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
from unittest import mock

from warm_logic.kernel.mesh.capabilities import CapabilityRegistry, PeerCapability


class TestCapabilitiesSaturation(unittest.TestCase):
    def test_get_local_capabilities_riscv(self):
        # Line 39: riscv in platform.machine()
        with mock.patch("platform.machine", return_value="riscv64"):
            caps = CapabilityRegistry.get_local_capabilities()
            self.assertEqual(caps[PeerCapability.SENSOR_STREAM.name], 100)

    def test_get_local_capabilities_import_fail(self):
        # Line 47: except ImportError
        with mock.patch("importlib.import_module", side_effect=ImportError()):
            caps = CapabilityRegistry.get_local_capabilities()
            self.assertNotIn(PeerCapability.PQC_VALIDATION.name, caps)

    def test_verify_capability_score_bounds(self):
        # Line 76-78: score > 100 or score < 0
        self.assertFalse(CapabilityRegistry.verify_capability_score({"cap": 101}))
        self.assertFalse(CapabilityRegistry.verify_capability_score({"cap": -1}))
        self.assertTrue(CapabilityRegistry.verify_capability_score({"cap": 50}))

    def test_is_root_authority_threshold(self):
        # Line 83: score >= 80
        self.assertTrue(
            CapabilityRegistry.is_root_authority({PeerCapability.LLM_REASONING.name: 80})
        )
        self.assertFalse(
            CapabilityRegistry.is_root_authority({PeerCapability.LLM_REASONING.name: 79})
        )

    def test_benchmark_cpu(self):
        # Exercise benchmark_cpu_performance
        score = CapabilityRegistry.benchmark_cpu_performance()
        self.assertGreaterEqual(score, 1)


if __name__ == "__main__":
    unittest.main()
