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
"""
Comprehensive tests for substrate/proof_generator.py - ZK Proof Generation
Target: 80%+ coverage
"""

import hashlib
import importlib
import json
import sys
import unittest
from unittest.mock import MagicMock, patch


def _reload_proof_generator():
    """Reload proof_generator module to ensure clean state."""
    import warm_logic.kernel.substrate.proof_generator as pg_module

    importlib.reload(pg_module)
    return pg_module.ProofGenerator


class TestProofGeneratorGenerateProof(unittest.TestCase):
    """Test generate_proof method."""

    def test_generate_proof_no_rust_core(self):
        """Test that generate_proof raises when Rust core is missing."""
        context = {"action": "test", "user": "alice"}
        verdict = True

        # Create mock module
        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = False
        mock_rl.rust_core = None

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()

            with self.assertRaises(RuntimeError) as ctx:
                ProofGenerator.generate_proof(context, verdict)

            self.assertIn("Rust Core missing", str(ctx.exception))

    def test_generate_proof_rust_core_none(self):
        """Test that generate_proof raises when rust_core is None."""
        context = {"action": "test"}
        verdict = True

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = None

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()

            with self.assertRaises(RuntimeError) as ctx:
                ProofGenerator.generate_proof(context, verdict)

            self.assertIn("Rust Core missing", str(ctx.exception))

    def test_generate_proof_success_true_verdict(self):
        """Test successful proof generation with True verdict."""
        context = {"action": "approve", "user": "bob"}
        verdict = True

        mock_zkp = MagicMock()
        mock_zkp.commitment_hex = "commitment123"
        mock_zkp.proof_hex = "proof456"

        mock_gen = MagicMock()
        mock_gen.generate_state_proof.return_value = mock_zkp

        mock_rust_core = MagicMock()
        mock_rust_core.RustZKProofGenerator.return_value = mock_gen

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            proof_json = ProofGenerator.generate_proof(context, verdict)

        proof_obj = json.loads(proof_json)
        self.assertEqual(proof_obj["prefix"], "zkp_v2_sigma_sp1")
        self.assertEqual(proof_obj["commitment"], "commitment123")
        self.assertEqual(proof_obj["proof"], "proof456")
        self.assertTrue(proof_obj["meta"]["verdict"])

    def test_generate_proof_success_false_verdict(self):
        """Test successful proof generation with False verdict."""
        context = {"action": "reject", "reason": "invalid"}
        verdict = False

        mock_zkp = MagicMock()
        mock_zkp.commitment_hex = "commit_false"
        mock_zkp.proof_hex = "proof_false"

        mock_gen = MagicMock()
        mock_gen.generate_state_proof.return_value = mock_zkp

        mock_rust_core = MagicMock()
        mock_rust_core.RustZKProofGenerator.return_value = mock_gen

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            proof_json = ProofGenerator.generate_proof(context, verdict)

        proof_obj = json.loads(proof_json)
        self.assertFalse(proof_obj["meta"]["verdict"])

        # Verify value passed to generate_state_proof is 0 for False
        call_args = mock_gen.generate_state_proof.call_args
        self.assertEqual(call_args[0][0], 0)

    def test_generate_proof_context_hash(self):
        """Test that context is properly hashed."""
        context = {"key": "value", "number": 42}
        verdict = True

        mock_zkp = MagicMock()
        mock_zkp.commitment_hex = "commit"
        mock_zkp.proof_hex = "proof"

        mock_gen = MagicMock()
        mock_gen.generate_state_proof.return_value = mock_zkp

        mock_rust_core = MagicMock()
        mock_rust_core.RustZKProofGenerator.return_value = mock_gen

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            proof_json = ProofGenerator.generate_proof(context, verdict)

        proof_obj = json.loads(proof_json)
        expected_hash = hashlib.sha256(
            json.dumps(context, sort_keys=True).encode()
        ).hexdigest()
        self.assertEqual(proof_obj["meta"]["ctx_hash"], expected_hash)

    def test_generate_proof_rust_exception(self):
        """Test that exceptions from Rust core are wrapped."""
        context = {"action": "test"}
        verdict = True

        mock_gen = MagicMock()
        mock_gen.generate_state_proof.side_effect = Exception("Rust error")

        mock_rust_core = MagicMock()
        mock_rust_core.RustZKProofGenerator.return_value = mock_gen

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()

            with self.assertRaises(RuntimeError) as ctx:
                ProofGenerator.generate_proof(context, verdict)

            self.assertIn("zkVM Proof Generation Failed", str(ctx.exception))


class TestProofGeneratorVerifyProof(unittest.TestCase):
    """Test verify_proof method."""

    def test_verify_proof_no_rust_core(self):
        """Test verify_proof returns False when Rust core is missing."""
        proof_json = '{"prefix": "zkp_v2_sigma_sp1"}'
        context = {"action": "test"}
        verdict = True

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = False
        mock_rl.rust_core = None

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertFalse(result)

    def test_verify_proof_rust_core_none(self):
        """Test verify_proof returns False when rust_core is None."""
        proof_json = '{"prefix": "zkp_v2_sigma_sp1"}'
        context = {"action": "test"}
        verdict = True

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = None

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertFalse(result)

    def test_verify_proof_invalid_json(self):
        """Test verify_proof returns False for invalid JSON."""
        proof_json = "not valid json"
        context = {"action": "test"}
        verdict = True

        mock_rust_core = MagicMock()

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertFalse(result)

    def test_verify_proof_wrong_prefix(self):
        """Test verify_proof returns False for wrong prefix."""
        proof_json = '{"prefix": "wrong_prefix"}'
        context = {"action": "test"}
        verdict = True

        mock_rust_core = MagicMock()

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertFalse(result)

    def test_verify_proof_context_hash_mismatch(self):
        """Test verify_proof returns False when context hash doesn't match."""
        context = {"action": "test"}
        verdict = True

        proof_obj = {
            "prefix": "zkp_v2_sigma_sp1",
            "commitment": "commit",
            "proof": "proof",
            "meta": {
                "ctx_hash": "wrong_hash",
                "verdict": True,
            },
        }
        proof_json = json.dumps(proof_obj)

        mock_rust_core = MagicMock()

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertFalse(result)

    def test_verify_proof_verdict_mismatch(self):
        """Test verify_proof returns False when verdict doesn't match."""
        context = {"action": "test"}

        ctx_json = json.dumps(context, sort_keys=True)
        ctx_hash = hashlib.sha256(ctx_json.encode()).hexdigest()

        proof_obj = {
            "prefix": "zkp_v2_sigma_sp1",
            "commitment": "commit",
            "proof": "proof",
            "meta": {
                "ctx_hash": ctx_hash,
                "verdict": True,  # Proof says True
            },
        }
        proof_json = json.dumps(proof_obj)

        mock_rust_core = MagicMock()

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            # But we verify with False
            result = ProofGenerator.verify_proof(proof_json, context, False)
            self.assertFalse(result)

    def test_verify_proof_success(self):
        """Test successful proof verification."""
        context = {"action": "test", "user": "alice"}
        verdict = True

        ctx_json = json.dumps(context, sort_keys=True)
        ctx_hash = hashlib.sha256(ctx_json.encode()).hexdigest()

        proof_obj = {
            "prefix": "zkp_v2_sigma_sp1",
            "commitment": "valid_commit",
            "proof": "valid_proof",
            "meta": {
                "ctx_hash": ctx_hash,
                "verdict": True,
            },
        }
        proof_json = json.dumps(proof_obj)

        mock_gen = MagicMock()
        mock_gen.verify_state_proof.return_value = True

        mock_rust_core = MagicMock()
        mock_rust_core.RustZKProofGenerator.return_value = mock_gen

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertTrue(result)

        # Verify the correct args were passed
        mock_gen.verify_state_proof.assert_called_once_with(
            "valid_proof", "valid_commit"
        )

    def test_verify_proof_verification_fails(self):
        """Test verify_proof returns False when Rust verification fails."""
        context = {"action": "test"}
        verdict = True

        ctx_json = json.dumps(context, sort_keys=True)
        ctx_hash = hashlib.sha256(ctx_json.encode()).hexdigest()

        proof_obj = {
            "prefix": "zkp_v2_sigma_sp1",
            "commitment": "commit",
            "proof": "proof",
            "meta": {
                "ctx_hash": ctx_hash,
                "verdict": True,
            },
        }
        proof_json = json.dumps(proof_obj)

        mock_gen = MagicMock()
        mock_gen.verify_state_proof.return_value = False

        mock_rust_core = MagicMock()
        mock_rust_core.RustZKProofGenerator.return_value = mock_gen

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertFalse(result)

    def test_verify_proof_rust_exception(self):
        """Test verify_proof returns False when Rust raises exception."""
        context = {"action": "test"}
        verdict = True

        ctx_json = json.dumps(context, sort_keys=True)
        ctx_hash = hashlib.sha256(ctx_json.encode()).hexdigest()

        proof_obj = {
            "prefix": "zkp_v2_sigma_sp1",
            "commitment": "commit",
            "proof": "proof",
            "meta": {
                "ctx_hash": ctx_hash,
                "verdict": True,
            },
        }
        proof_json = json.dumps(proof_obj)

        mock_gen = MagicMock()
        mock_gen.verify_state_proof.side_effect = Exception("Rust error")

        mock_rust_core = MagicMock()
        mock_rust_core.RustZKProofGenerator.return_value = mock_gen

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertFalse(result)


class TestProofGeneratorIntegration(unittest.TestCase):
    """Integration tests for proof round-trip."""

    def test_generate_and_verify_roundtrip(self):
        """Test that a generated proof can be verified."""
        context = {"action": "approve", "resource": "document-123"}
        verdict = True

        mock_zkp = MagicMock()
        mock_zkp.commitment_hex = "commitment_abc"
        mock_zkp.proof_hex = "proof_xyz"

        mock_gen = MagicMock()
        mock_gen.generate_state_proof.return_value = mock_zkp
        mock_gen.verify_state_proof.return_value = True

        mock_rust_core = MagicMock()
        mock_rust_core.RustZKProofGenerator.return_value = mock_gen

        mock_rl = MagicMock()
        mock_rl.HAS_RUST_CORE = True
        mock_rl.rust_core = mock_rust_core

        with patch.dict(sys.modules, {"warm_logic.kernel.rust_loader": mock_rl}):
            ProofGenerator = _reload_proof_generator()

            # Generate
            proof_json = ProofGenerator.generate_proof(context, verdict)

            # Verify
            result = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
