import time
import unittest

from warm_logic.kernel.formal.verifier import PatchVerifier
from warm_logic.kernel.provenance.ledger import GlobalLedger


class TestSovereignMath(unittest.TestCase):
    def test_invariant_preservation(self):
        """Verify PatchVerifier rejects Constitution deletion (Suicide Patch)."""
        suicide_code = """
class SovereignConstitution:
    pass

del SovereignConstitution
"""
        is_safe, violations = PatchVerifier.verify_patch(suicide_code)
        self.assertFalse(is_safe)
        self.assertTrue(any("delete 'SovereignConstitution'" in v for v in violations))
        print("✅ Verified: Suicide Patch REJECTED.")

    def test_invariant_safety(self):
        """Verify PatchVerifier rejects Shell Injection."""
        unsafe_code = """
import os
def hack():
    os.system("rm -rf /")
"""
        is_safe, violations = PatchVerifier.verify_patch(unsafe_code)
        self.assertFalse(is_safe)
        self.assertTrue(any("os.system" in v for v in violations))
        print("✅ Verified: Unsafe Shell REJECTED.")

    def test_ledger_integrity(self):
        """Verify GlobalLedger Proof-of-History hash chaining."""
        ledger = GlobalLedger(":memory:")

        # 1. Anchorage
        h1 = ledger.append_state("State_A")
        h2 = ledger.append_state("State_B")

        self.assertTrue(ledger.verify_chain())
        print(f"✅ Verified: Honest Chain valid. Height: {len(ledger.chain)}")

        # 2. Tampering Attack (Rewriting History)
        # Attacker tries to change State_A in the past
        ledger.chain[1].state_hash = "State_A_HACKED"

        # Verification should fail because hash of block 1 no longer matches block 2's previous_hash
        # Wait, simply changing state_hash doesn't change computed hash unless we recompute?
        # The verification recomputes previous.compute_hash().

        self.assertFalse(ledger.verify_chain())
        print("✅ Verified: Tampered Chain REJECTED.")


if __name__ == "__main__":
    unittest.main()
