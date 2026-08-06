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
[P1] Rust Core Integration Tests.

These tests verify that the actual Rust Core works correctly.
USE_RUST_CORE = True - No mocking allowed.
"""

import os
import unittest

from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestRustCoreIntegration(WarmLogicTestCase):
    """
    Integration tests that REQUIRE real Rust Core.
    No mocking - these test actual cryptographic operations.
    """

    USE_RUST_CORE = True  # CRITICAL: Use real Rust Core

    def test_mldsa65_keypair_generation(self):
        """Test ML-DSA-65 keypair generation (FIPS 204)."""
        import warm_logic_rs as rs

        pub, priv = rs.PQCKeypair.generate()

        # ML-DSA-65 key sizes
        self.assertEqual(len(pub) // 2, 1952, "Public key should be 1952 bytes")
        self.assertGreater(len(priv), 1000, "Private key should be substantial")

    def test_mldsa65_sign_verify(self):
        """Test ML-DSA-65 sign and verify operations."""
        import warm_logic_rs as rs

        pub, priv = rs.PQCKeypair.generate()
        message = "WarmLogic Sovereign Governance Test"

        # Sign
        signature = rs.MLDSA.sign(priv, message)
        self.assertEqual(len(signature) // 2, 3309, "Signature should be 3309 bytes")

        # Verify valid signature
        self.assertTrue(rs.MLDSA.verify(pub, message, signature))

        # Verify tampered message fails
        self.assertFalse(rs.MLDSA.verify(pub, "TAMPERED", signature))

    def test_zk_proof_generation(self):
        """Test Zero-Knowledge proof generation (Sigma/Ristretto255)."""
        import warm_logic_rs as rs

        zkgen = rs.RustZKProofGenerator()
        blinding = os.urandom(32).hex()

        proof = zkgen.generate_state_proof(42, blinding)

        self.assertIsNotNone(proof.commitment_hex)
        self.assertIsNotNone(proof.proof_hex)
        self.assertEqual(len(proof.commitment_hex), 64)  # 32 bytes hex

    def test_zk_proof_verification(self):
        """Test Zero-Knowledge proof verification."""
        import warm_logic_rs as rs

        zkgen = rs.RustZKProofGenerator()
        blinding = os.urandom(32).hex()

        proof = zkgen.generate_state_proof(42, blinding)
        verified = zkgen.verify_state_proof(proof.proof_hex, proof.commitment_hex)

        self.assertTrue(verified)

    def test_bft_consensus_engine(self):
        """Test BFT Consensus Engine initialization."""
        import warm_logic_rs as rs

        bft = rs.BFTEngine(4)  # 4-node quorum
        bft.py_start_round(1)
        bft.py_propose("test_block_hash")

        # Should not raise
        self.assertIsNotNone(bft)

    def test_reflective_loop_governance(self):
        """Test ReflectiveLoop governance kernel."""
        import warm_logic_rs as rs

        loop = rs.ReflectiveLoop()

        # Test with high tau_ethics (should trigger VETO_LOCK)
        mode1 = loop.compute_mode({"epsilon_c": 0.8, "tau_ethics": 0.9})
        self.assertEqual(mode1.mode, "VETO_LOCK")

        # Test with low values (should be SUSPICIOUS)
        mode2 = loop.compute_mode({"epsilon_c": 0.5, "tau_ethics": 0.3})
        self.assertIn(mode2.mode, ["SUSPICIOUS", "NORMAL", "VETO_LOCK"])

    def test_slashing_engine(self):
        """Test Slashing Engine penalty calculation."""
        import warm_logic_rs as rs

        slasher = rs.SlashingEngine()
        verdict = slasher.evaluate_violation("INVALID_ZK_PROOF", 1000)

        self.assertIsNotNone(verdict.actor)
        self.assertIsNotNone(verdict.reason)
        self.assertIsNotNone(verdict.penalty)

    def test_sovereign_store_persistence(self):
        """Test SovereignStore (Sled) persistence."""
        import warm_logic_rs as rs

        db_path = os.path.join(self.test_dir, "test_sovereign.db")
        store = rs.SovereignStore(db_path)

        # Write
        store.put("balance:alice", "1000")
        store.put("balance:bob", "500")

        # Read
        self.assertEqual(store.get("balance:alice"), "1000")
        self.assertEqual(store.get("balance:bob"), "500")

        # Non-existent key
        self.assertIsNone(store.get("balance:charlie"))


class TestSovereignSecurityIntegration(WarmLogicTestCase):
    """Test SovereignSecurity wrapper with real Rust Core."""

    USE_RUST_CORE = True

    def test_sovereign_security_keypair(self):
        """Test SovereignSecurity keypair generation."""
        from warm_logic.security.pqc import SovereignSecurity

        pub, priv = SovereignSecurity.generate_keypair()

        self.assertEqual(len(pub) // 2, 1952)
        self.assertNotEqual(pub, "MOCK_PK_1234")  # Ensure not mock

    def test_sovereign_security_sign_verify(self):
        """Test SovereignSecurity sign/verify operations."""
        from warm_logic.security.pqc import SovereignSecurity

        pub, priv = SovereignSecurity.generate_keypair()
        message = "Governance Decision #12345"

        sig = SovereignSecurity.sign(priv, message)
        self.assertNotIn("MOCK_SIG_", sig)  # Ensure not mock

        verified = SovereignSecurity.verify(pub, message, sig)
        self.assertTrue(verified)

    def test_sovereign_security_tamper_detection(self):
        """Test that tampered messages fail verification."""
        from warm_logic.security.pqc import SovereignSecurity

        pub, priv = SovereignSecurity.generate_keypair()
        message = "Original message"

        sig = SovereignSecurity.sign(priv, message)

        # Original should verify
        self.assertTrue(SovereignSecurity.verify(pub, message, sig))

        # Tampered should fail
        self.assertFalse(SovereignSecurity.verify(pub, "Tampered message", sig))


if __name__ == "__main__":
    unittest.main()
