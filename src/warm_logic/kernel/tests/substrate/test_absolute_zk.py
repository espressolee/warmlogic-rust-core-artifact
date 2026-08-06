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
from unittest.mock import patch

from warm_logic.kernel.substrate.proof_zk import ZKProofGenerator


class TestAbsoluteZK(unittest.TestCase):
    @patch("warm_logic.kernel.substrate.proof_zk.HAS_RUST_CORE", True)
    @patch("warm_logic.kernel.substrate.proof_zk.rust_core")
    def test_bulletproofs_generation(self, mock_rs):
        """Verifies that ZK generation now requires Rust and produces v2 proofs."""
        mock_gen = mock_rs.RustZKProofGenerator.return_value
        mock_zkp = mock_gen.generate_state_proof.return_value
        mock_zkp.commitment_hex = "c_hex"
        mock_zkp.proof_hex = "p_hex"

        # Should work via Rust
        proof_json = ZKProofGenerator.generate_proof("r1", [{"tx": "data"}], "r2")
        proof_obj = json.loads(proof_json)

        self.assertEqual(proof_obj["prefix"], "zkp_v2_bulletproofs")
        self.assertEqual(proof_obj["commitment"], "c_hex")
        self.assertEqual(proof_obj["proof"], "p_hex")

    @patch("warm_logic.kernel.substrate.proof_zk.HAS_RUST_CORE", True)
    @patch("warm_logic.kernel.substrate.proof_zk.rust_core")
    def test_bulletproofs_verification(self, mock_rs):
        """Verifies real Bulletproofs verification logic."""
        mock_gen = mock_rs.RustZKProofGenerator.return_value
        # Mock generation output
        mock_zkp = mock_gen.generate_state_proof.return_value
        mock_zkp.commitment_hex = "c_hex"
        mock_zkp.proof_hex = "p_hex"

        # Mock verification output
        mock_gen.verify_state_proof.return_value = True

        prev_root = "root_old"
        txs = [{"id": 1}, {"id": 2}]
        new_root = "root_new"

        proof_json = ZKProofGenerator.generate_proof(prev_root, txs, new_root)

        # Valid verification
        self.assertTrue(
            ZKProofGenerator.verify_proof(proof_json, prev_root, txs, new_root)
        )

        # Tampered commitment should fail (due to strict meta check in python)
        proof_obj = json.loads(proof_json)
        proof_obj["meta"]["orig_commitment"] = "BAD"
        self.assertFalse(
            ZKProofGenerator.verify_proof(
                json.dumps(proof_obj), prev_root, txs, new_root
            )
        )

        # Verification fail from Rust
        mock_gen.verify_state_proof.return_value = False
        self.assertFalse(
            ZKProofGenerator.verify_proof(proof_json, prev_root, txs, new_root)
        )


if __name__ == "__main__":
    unittest.main()
