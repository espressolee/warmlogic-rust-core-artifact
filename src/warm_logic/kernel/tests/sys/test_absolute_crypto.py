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

from warm_logic.kernel.sys.cryptography import (
    MLDSA,
    KineticSovereign,
    QuantumEnclave,
    StateAttestor,
)


class TestCryptoCluster(unittest.TestCase):
    def setUp(self):
        """Reset StateAttestor singleton state before each test."""
        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None

    def test_mldsa(self):
        m = MLDSA()
        # Should now WORK via Rust
        kp = m.generate_keypair()
        self.assertTrue(len(kp.public_key) > 0)
        self.assertTrue(len(kp.private_key) > 0)

        msg = "ground truth"
        sig = m.sign(msg, kp.private_key)
        self.assertTrue(len(sig) > 0)
        self.assertTrue(m.verify(msg, sig, kp.public_key))
        self.assertFalse(m.verify("Tampered", sig, kp.public_key))

    def test_attestor(self):
        """Test StateAttestor works in development mode with Rust Core."""
        sa = StateAttestor()

        # With Rust Core available, StateAttestor now works in dev mode
        # (hardware sealing unavailable but proceeds with warning)
        attestation = sa.attest_state("test_hash_123")
        self.assertIn("attestation", attestation)
        self.assertIn("signature", attestation)
        self.assertIn("public_key", attestation)

        # sign_state should also work
        signature = sa.sign_state("test_hash_456")
        self.assertTrue(len(signature) > 0)

    def test_enclave(self):
        with self.assertRaises(RuntimeError):
            QuantumEnclave()

    def test_kinetic_sovereign(self):
        # 1. Verify Real Hardware ID Retrieval (No Mocks)
        # In this environment, we expect either a real ID or 'de43ce6b345bf247' (Simulated)
        hw_uuid = KineticSovereign.get_hardware_uuid()
        self.assertTrue(len(hw_uuid) > 0)

        # Should now WORK via Rust
        seed = KineticSovereign.get_kinetic_seed()
        self.assertTrue(len(seed) > 0)

        genesis = KineticSovereign.bind_genesis()
        self.assertTrue(len(genesis) == 64)  # SHA256
