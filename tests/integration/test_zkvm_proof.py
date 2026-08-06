import hashlib
import json
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from warm_logic.kernel import rust_loader
from warm_logic.kernel.substrate.proof_generator import ProofGenerator


class _FakeRustZKProofGenerator:
    """Deterministic Rust-zk shim used when extension artifacts are unavailable."""

    def generate_state_proof(self, value: int, blinding: str):
        digest = hashlib.sha256(f"{value}:{blinding}".encode()).hexdigest()
        return SimpleNamespace(commitment_hex=digest[:32], proof_hex=digest[32:])

    def verify_state_proof(self, proof_hex: str, commitment_hex: str) -> bool:
        return bool(proof_hex and commitment_hex)


class TestProofGeneratorIntegration(unittest.TestCase):
    def test_generate_verify_cycle(self):
        fake_core = SimpleNamespace(RustZKProofGenerator=_FakeRustZKProofGenerator)
        patch_kwargs = (
            {"HAS_RUST_CORE": True, "rust_core": fake_core}
            if not rust_loader.HAS_RUST_CORE or rust_loader.rust_core is None
            else {}
        )
        patch_context = (
            patch.multiple(rust_loader, **patch_kwargs)
            if patch_kwargs
            else nullcontext()
        )

        with patch_context:
            context = {
                "action": "governance_vote",
                "proposal_id": "BP-101",
                "voter": "Sovereign-01",
            }
            verdict = True

            # 1. Generate Proof
            proof_json = ProofGenerator.generate_proof(context, verdict)
            self.assertIsNotNone(proof_json)

            proof_obj = json.loads(proof_json)
            self.assertEqual(proof_obj["prefix"], "zkp_v2_sigma_sp1")
            self.assertEqual(proof_obj["meta"]["verdict"], verdict)

            # 2. Verify Proof (Success case)
            is_valid = ProofGenerator.verify_proof(proof_json, context, verdict)
            self.assertTrue(is_valid, "Correct proof should verify successfully")

            # 3. Verify Proof (Tampered context)
            wrong_context = context.copy()
            wrong_context["proposal_id"] = "BP-102"
            is_valid_wrong_ctx = ProofGenerator.verify_proof(
                proof_json, wrong_context, verdict
            )
            self.assertFalse(
                is_valid_wrong_ctx, "Tampered context should fail verification"
            )

            # 4. Verify Proof (Tampered verdict)
            is_valid_wrong_verdict = ProofGenerator.verify_proof(
                proof_json, context, not verdict
            )
            self.assertFalse(
                is_valid_wrong_verdict, "Tampered verdict should fail verification"
            )


if __name__ == "__main__":
    unittest.main()
