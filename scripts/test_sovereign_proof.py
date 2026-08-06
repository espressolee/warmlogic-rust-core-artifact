""" Proof of Sovereignty (ZK-Proof) Verification.
Tests Integrity Binding and Anti-Tamper properties.
"""

import json
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.justice.audit_ledger import AuditLedger
from warm_logic.kernel.justice.proof_verifier import ProofVerifier
from warm_logic.kernel.justice.refusal import RefusalEngine


class TestSovereignProof(unittest.TestCase):
    def setUp(self):
        self.engine = RefusalEngine()
        self.ledger = AuditLedger()

    def test_proof_generation_and_verification(self):
        """Verify that a valid execution produces a verifiable proof."""
        print("Testing Proof: Generation & Valid Verification...")
        ctx = {
            "remote_attestation": {"tee_type": "AWSNitro"},
            "mesh_latch_active": False,
            "sieve_verdict": "ALLOW",
        }

        # 1. Run engine
        self.engine.enforce_sovereignty(ctx)

        # 2. Retrieve last event from ledger
        events = self.ledger.get_events()
        last_event = events[-1]
        proof = last_event["data"]["sovereign_proof"]
        verdict = last_event["event_type"] == "ACCESS_GRANTED"

        print(f"   Generated Proof: {proof[:16]}...")

        # 3. Verify
        is_valid = ProofVerifier.verify_proof(proof, ctx, verdict)
        self.assertTrue(is_valid)

    def test_proof_anti_tamper(self):
        """Verify that tampering with context invalidates the proof."""
        print("Testing Invariant: Anti-Tamper (Invalidates Proof)...")
        ctx = {
            "remote_attestation": {"tee_type": "AWSNitro"},
            "mesh_latch_active": False,
            "sieve_verdict": "ALLOW",
        }

        # 1. Run engine
        self.engine.enforce_sovereignty(ctx)

        # 2. Retrieve proof
        events = self.ledger.get_events()
        last_event = events[-1]
        proof = last_event["data"]["sovereign_proof"]
        verdict = last_event["event_type"] == "ACCESS_GRANTED"

        # 3. TAMPER with context
        tampered_ctx = ctx.copy()
        tampered_ctx["mesh_latch_active"] = True  # Maliciously change history

        # 4. Verify (Should FAIL)
        is_valid = ProofVerifier.verify_proof(proof, tampered_ctx, verdict)
        self.assertFalse(is_valid)
        print("   Verification correctly REJECTED tampered context.")


if __name__ == "__main__":
    unittest.main()
