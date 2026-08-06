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

from warm_logic.kernel.ops.compiler import PacketManifest, PassCompiler
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestCompilerCoverage(WarmLogicTestCase):
    def test_compiler_success(self):
        pc = PassCompiler(hardware_id="HW-001")

        def mock_policy(inputs):
            return True, "SUCCESS"

        inputs = {"id": "intent-1", "data": "test"}
        manifest = pc.compile_intent(inputs, mock_policy)

        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.intent_id, "intent-1")
        self.assertEqual(manifest.verdict, "APPROVED")
        self.assertEqual(manifest.integrity_score, 0.0)

    def test_compiler_rejection(self):
        pc = PassCompiler(hardware_id="HW-001")

        def mock_policy(inputs):
            return False, "DENIED"

        inputs = {"id": "intent-bad"}
        manifest = pc.compile_intent(inputs, mock_policy)
        self.assertIsNone(manifest)

    def test_compiler_empty_inputs(self):
        pc = PassCompiler(hardware_id="HW-001")
        self.assertIsNone(pc.compile_intent({}, lambda x: (True, "OK")))

    def test_compiler_crash(self):
        pc = PassCompiler(hardware_id="HW-001")

        def crashing_policy(inputs):
            raise ValueError("BOOM")

        with self.assertLogs("PassCompiler", level="ERROR") as cm:
            manifest = pc.compile_intent({"id": "x"}, crashing_policy)
            self.assertIsNone(manifest)
            self.assertIn("PassCompiler CRASH", cm.output[0])

    def test_packet_manifest_defaults(self):
        pm = PacketManifest(intent_id="i1", verdict="OK")
        self.assertEqual(pm.provenance, "WarmLogic_v1")
        self.assertEqual(pm.integrity_score, 0.0)
