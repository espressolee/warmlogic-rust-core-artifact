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
from unittest.mock import MagicMock, patch

from warm_logic.kernel.autonomy.patcher import AutonomousPatcher, LogicGap


class TestAutonomySurgical(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.patcher = AutonomousPatcher(root_path="/tmp", store=self.mock_store)

    async def test_patcher_apply_stub(self):
        # Create a mock file with a NotImplementedError
        test_file = "/tmp/test_patch.py"
        with open(test_file, "w") as f:
            f.write("def dummy():\n    raise NotImplementedError('Fix me')\n")

        gap = LogicGap(
            file_path=test_file,
            line_number=2,
            description="Test Gap",
            gap_type="NotImplemented",
        )

        # Test Stub Strategy
        success = await self.patcher.apply_patch(gap, strategy="stub")
        self.assertTrue(success)

        with open(test_file, "r") as f:
            content = f.read()
            self.assertIn("[AUTOPATCH] Stubbed logic", content)
            self.assertIn("pass", content)

    def test_verify_patch_safety(self):
        test_file = "/tmp/safe_patch.py"
        with open(test_file, "w") as f:
            f.write("import os\nprint('hello')\n")

        self.assertTrue(self.patcher.verify_patch_safety(test_file))

        # Test invalid syntax
        with open(test_file, "w") as f:
            f.write("if True\n    pass\n")
        self.assertFalse(self.patcher.verify_patch_safety(test_file))

    def test_rollback(self):
        test_file = "/tmp/rollback_test.py"
        bak_file = test_file + ".bak"
        with open(test_file, "w") as f:
            f.write("new")
        with open(bak_file, "w") as f:
            f.write("old")

        self.patcher.rollback(test_file)
        with open(test_file, "r") as f:
            self.assertEqual(f.read(), "old")


class TestAutonomyExtra(unittest.TestCase):
    def test_council_basics(self):
        from warm_logic.kernel.autonomy.governance import CouncilOfThree

        council = CouncilOfThree()
        # Should return true for anything reasonable in mock mode
        self.assertTrue(council.review_patch("print(1)", "assert True", "test"))

    def test_reasoning_basics(self):
        from warm_logic.kernel.autonomy.reasoning import ReasoningSynthesizer

        rs = ReasoningSynthesizer()
        body, test = rs.synthesize_logic("calc", "add 1", strategy="semantic")
        self.assertIsInstance(body, str)
        self.assertIsInstance(test, str)


class TestMeshSyncSurgical(unittest.IsolatedAsyncioTestCase):
    async def test_logos_propagator_lifecycle(self):
        from warm_logic.kernel.autonomy.mesh_sync import LogosPropagator

        mock_dht = MagicMock()
        mock_dht.node_id = b"localnodeid"
        mock_galaxy = MagicMock()
        # Mock Enclave and PQC to avoid complex init
        with patch(
            "warm_logic.security.pqc.SovereignSecurity.generate_keypair",
            return_value=(b"pk", b"sk"),
        ):
            with patch("warm_logic.security.enclave.HardwareEnclave"):
                prop = LogosPropagator(mock_dht, mock_galaxy, root_path="/tmp")

                # Test announce_mutation (requires logos bundler mock)
                prop.bundler = MagicMock()
                prop.bundler.create_bundle.return_value = (b"bundle", "hash")
                prop.bundler.sign_bundle.return_value = b"sig"

                msg = await prop.announce_mutation()
                self.assertEqual(msg["manifest_hash"], "hash")

                # Clear current manifest to test handle_logos_manifest logic
                prop.current_manifest = None

                # Test handle_logos_manifest
                prop.bundler.verify_bundle.return_value = True
                msg["origin"] = "node1"
                result = await prop.handle_logos_manifest(msg)
                # Should return False first because quorum_threshold=2
                self.assertFalse(result)

                # Second vote
                msg["origin"] = "node2"
                result = await prop.handle_logos_manifest(msg)
                self.assertTrue(result)
