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
ML-KEM-768 (FIPS 203) Post-Quantum Key Encapsulation Tests

Tests the ML-KEM-768 implementation for quantum-resistant key exchange.
FIPS 203 standardized algorithm for NIST PQC competition.
"""

import unittest

from warm_logic.kernel import rust_loader


class TestMLKEM768(unittest.TestCase):
    """
    ML-KEM-768 Post-Quantum Key Exchange
    FIPS 203 compliant implementation.
    """

    @classmethod
    def setUpClass(cls):
        """Ensure Rust core is loaded."""
        if not rust_loader.HAS_RUST_CORE:
            raise unittest.SkipTest("Rust core not available")
        cls.rs = rust_loader.load_rust_core()

    def test_kem_keygen_key_sizes(self):
        """Test ML-KEM-768 key generation produces correct key sizes."""
        ek, dk = self.rs.kem_keygen()
        # ML-KEM-768 key sizes: EK=1184 bytes, DK=2400 bytes
        self.assertEqual(len(ek) // 2, 1184, "Encapsulation key should be 1184 bytes")
        self.assertEqual(len(dk) // 2, 2400, "Decapsulation key should be 2400 bytes")

    def test_kem_encapsulate_output_sizes(self):
        """Test ML-KEM-768 encapsulation produces correct output sizes."""
        ek, _ = self.rs.kem_keygen()
        ss, ct = self.rs.kem_encapsulate(ek)
        # ML-KEM-768: Shared secret=32 bytes, Ciphertext=1088 bytes
        self.assertEqual(len(ss) // 2, 32, "Shared secret should be 32 bytes")
        self.assertEqual(len(ct) // 2, 1088, "Ciphertext should be 1088 bytes")

    def test_kem_roundtrip(self):
        """Test complete ML-KEM-768 key exchange roundtrip."""
        # Alice generates keypair
        ek, dk = self.rs.kem_keygen()

        # Bob encapsulates a shared secret using Alice's encapsulation key
        ss_bob, ct = self.rs.kem_encapsulate(ek)

        # Alice decapsulates to get the same shared secret
        ss_alice = self.rs.kem_decapsulate(dk, ct)

        # Both parties should have the same shared secret
        self.assertEqual(ss_bob, ss_alice, "Shared secrets must match")

    def test_kem_wrong_decapsulation_key(self):
        """Test that decapsulation with wrong key fails gracefully."""
        # Generate two different keypairs
        ek1, dk1 = self.rs.kem_keygen()
        _, dk2 = self.rs.kem_keygen()

        # Encapsulate with first key
        ss1, ct = self.rs.kem_encapsulate(ek1)

        # Decapsulate with wrong (second) key - should produce different secret
        ss2 = self.rs.kem_decapsulate(dk2, ct)

        # Secrets should NOT match (ML-KEM implicit rejection)
        self.assertNotEqual(ss1, ss2, "Wrong key should produce different secret")

    def test_kem_invalid_key_length_errors(self):
        """Test that invalid key lengths produce errors."""
        with self.assertRaises(ValueError):
            self.rs.kem_encapsulate("deadbeef")  # Too short

        ek, dk = self.rs.kem_keygen()
        _, ct = self.rs.kem_encapsulate(ek)

        with self.assertRaises(ValueError):
            self.rs.kem_decapsulate("deadbeef", ct)  # Wrong dk length

    def test_mlkem_class_keygen(self):
        """Test MLKEM class static keygen method."""
        ek, dk = self.rs.MLKEM.keygen()
        self.assertEqual(len(ek) // 2, 1184)
        self.assertEqual(len(dk) // 2, 2400)

    def test_mlkem_class_encapsulate(self):
        """Test MLKEM class encapsulate method returns KEMEncapsResult."""
        ek, _ = self.rs.kem_keygen()
        result = self.rs.MLKEM.encapsulate(ek)

        # Result should have shared_secret and ciphertext attributes
        self.assertTrue(hasattr(result, "shared_secret"))
        self.assertTrue(hasattr(result, "ciphertext"))
        self.assertEqual(len(result.shared_secret) // 2, 32)
        self.assertEqual(len(result.ciphertext) // 2, 1088)

    def test_mlkem_class_roundtrip(self):
        """Test MLKEM class full roundtrip."""
        ek, dk = self.rs.MLKEM.keygen()
        result = self.rs.MLKEM.encapsulate(ek)
        ss = self.rs.MLKEM.decapsulate(dk, result.ciphertext)
        self.assertEqual(result.shared_secret, ss)

    def test_multiple_encapsulations_different_secrets(self):
        """Test that each encapsulation produces a different shared secret."""
        ek, dk = self.rs.kem_keygen()

        # Multiple encapsulations
        ss1, ct1 = self.rs.kem_encapsulate(ek)
        ss2, ct2 = self.rs.kem_encapsulate(ek)

        # Each should produce different secrets and ciphertexts
        self.assertNotEqual(ss1, ss2, "Each encapsulation should produce unique secret")
        self.assertNotEqual(
            ct1, ct2, "Each encapsulation should produce unique ciphertext"
        )

        # But decapsulation should work for both
        self.assertEqual(ss1, self.rs.kem_decapsulate(dk, ct1))
        self.assertEqual(ss2, self.rs.kem_decapsulate(dk, ct2))


if __name__ == "__main__":
    unittest.main()
