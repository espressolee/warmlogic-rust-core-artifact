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
import json
import unittest

from warm_logic.kernel.substrate.proof_generator import ProofGenerator
from warm_logic.kernel.substrate.proof_zk import ZKProofGenerator


class TestZKCluster(unittest.TestCase):
    def test_zk_proof_generator(self):
        # By-passing HAS_RUST_CORE for unit test logic if needed,
        # but let's just mock the generator calls so it works in all envs.
        from unittest.mock import MagicMock, patch

        # 1. Commitment
        c1 = ZKProofGenerator._compute_commitment("root1", ["tx1"], "root2")
        c2 = ZKProofGenerator._compute_commitment("root1", ["tx1"], "root2")
        self.assertEqual(c1, c2)

        # 2. Generate (Needs Rust mock)
        with patch("warm_logic.kernel.substrate.proof_zk.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.substrate.proof_zk.rust_core") as mock_core:
                mock_gen = MagicMock()
                mock_zkp = MagicMock()
                mock_zkp.commitment_hex = "comm"
                mock_zkp.proof_hex = "proof"
                mock_gen.generate_state_proof.return_value = mock_zkp
                mock_core.RustZKProofGenerator.return_value = mock_gen

                proof = ZKProofGenerator.generate_proof(
                    "a", ["t"], "b", prev_proof="old"
                )
                obj = json.loads(proof)

                self.assertEqual(obj["prefix"], "zkp_v2_bulletproofs")
                self.assertEqual(obj["meta"]["prev_state_root"], "a")

        # 3. Verify (Needs Rust mock)
        with patch("warm_logic.kernel.substrate.proof_zk.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.substrate.proof_zk.rust_core") as mock_core:
                mock_gen = MagicMock()
                mock_gen.verify_state_proof.return_value = True
                mock_core.RustZKProofGenerator.return_value = mock_gen

                self.assertTrue(ZKProofGenerator.verify_proof(proof, "a", ["t"], "b"))

        # 4. Verify - Failure Paths
        self.assertFalse(ZKProofGenerator.verify_proof("badjson", "a", [], "b"))
        self.assertFalse(ZKProofGenerator.verify_proof("[]", "a", [], "b"))  # Not dict

        obj["prefix"] = "bad"
        self.assertFalse(
            ZKProofGenerator.verify_proof(json.dumps(obj), "a", ["t"], "b")
        )

    def test_proof_generator_sp1(self):
        # hardware attestation enforcement: SP1 generation is disabled without Rust Core
        from unittest.mock import patch

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            with self.assertRaises(RuntimeError):
                ProofGenerator.generate_proof({"a": 1}, True)
