""" Formal Policy (Cedar) Verification.
Tests "Forbid-overrides-Permit" and policy-driven rejection.
"""

import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.justice.refusal import RefusalEngine


class TestFormalPolicy(unittest.TestCase):
    def setUp(self):
        self.engine = RefusalEngine()

    def test_policy_allow_nitro(self):
        """Verify AWSNitro is allowed by Permit policy."""
        print("Testing Policy: Permit AWSNitro...")
        ctx = {
            "remote_attestation": {"tee_type": "AWSNitro"},
            "mesh_latch_active": False,
            "sieve_verdict": "ALLOW",
        }
        self.assertTrue(self.engine.enforce_sovereignty(ctx))

    def test_policy_forbid_lockdown(self):
        """Verify Lockdown Forbid overrides Nitro Permit."""
        print("Testing Invariant: Forbid (Lockdown) overrides Permit (Nitro)...")
        ctx = {
            "remote_attestation": {"tee_type": "AWSNitro"},
            "mesh_latch_active": True,
            "sieve_verdict": "ALLOW",
        }
        with self.assertRaises(ValueError) as cm:
            self.engine.enforce_sovereignty(ctx)
        self.assertIn("MESH_LOCKDOWN", str(cm.exception))

    def test_policy_forbid_sieve(self):
        """Verify Sieve Block Forbid overrides Nitro Permit."""
        print("Testing Invariant: Forbid (Sieve) overrides Permit (Nitro)...")
        ctx = {
            "remote_attestation": {"tee_type": "AWSNitro"},
            "mesh_latch_active": False,
            "sieve_verdict": "BLOCK",
        }
        with self.assertRaises(ValueError) as cm:
            self.engine.enforce_sovereignty(ctx)
        self.assertIn("NEURAL_SIEVE_BLOCK", str(cm.exception))

    def test_policy_implicit_deny(self):
        """Verify GenericVM is denied (No permit)."""
        print("Testing Principle: Implicit Deny (GenericVM)...")
        ctx = {
            "remote_attestation": {"tee_type": "GenericVM"},
            "mesh_latch_active": False,
            "sieve_verdict": "ALLOW",
        }
        with self.assertRaises(ValueError) as cm:
            self.engine.enforce_sovereignty(ctx)
        self.assertIn("POLICY_VIOLATION", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
