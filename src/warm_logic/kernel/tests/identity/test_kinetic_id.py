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
from unittest.mock import MagicMock, patch

import warm_logic.kernel.identity.kinetic_id as kid
from warm_logic.kernel import rust_loader
from warm_logic.kernel.identity.kinetic_id import KineticIdentity


class TestKineticIdentity(unittest.TestCase):
    """
    Kinetic Identity Verification
    Target: 100% Line/Branch Coverage for kinetic_id.py
    """

    def test_init_generation(self):
        """Test generating a new keypair (Mocked)"""
        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("pub", "priv")
        # Patch at the module where it's used (kinetic_id imports rust_loader)
        with patch.object(kid, "rust_loader") as mock_loader:
            mock_loader.HAS_RUST_CORE = True
            mock_loader.load_rust_core.return_value = mock_rs
            identity = KineticIdentity()
            self.assertEqual(identity.public_key, "pub")
            self.assertEqual(identity.private_key, "priv")

    def test_init_provided_keys(self):
        """Test providing an existing keypair"""
        # Works even without Rust, as it bypasses generation
        # But we force True to ensure we test that branch if relevant
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            keys = ("pub_test", "priv_test")
            identity = KineticIdentity(keypair=keys)
            self.assertEqual(identity.public_key, "pub_test")
            self.assertEqual(identity.private_key, "priv_test")

    def test_sign_and_verify(self):
        """Test the end-to-end signing and verification flow (Mocked)"""
        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("pub", "priv")
        mock_rs.sign.return_value = "signature_mock"
        mock_rs.verify.return_value = True

        with patch.object(kid, "rust_loader") as mock_loader:
            mock_loader.HAS_RUST_CORE = True
            mock_loader.load_rust_core.return_value = mock_rs
            identity = KineticIdentity()
            payload = "intent::transfer::100"

            # Sign
            sig = identity.sign_intent(payload)
            self.assertEqual(sig, "signature_mock")

            # Verify (Success)
            is_valid = KineticIdentity.verify_intent(identity.public_key, payload, sig)
            self.assertTrue(is_valid)

            # Verify (Failure - simulated by mock returning False)
            mock_rs.verify.return_value = False
            is_valid_wrong = KineticIdentity.verify_intent("wrong_key", payload, sig)
            self.assertFalse(is_valid_wrong)

    def test_sign_without_key_error(self):
        """Test error when signing without a private key (simulated/edge case)"""
        if not rust_loader.HAS_RUST_CORE:
            return
        identity = KineticIdentity(keypair=("pub", None))
        with self.assertRaises(RuntimeError) as cm:
            identity.sign_intent("some intent")
        self.assertEqual(str(cm.exception), "Cannot sign without private key")

    def test_no_rust_graceful_handling(self):
        """
        Targeting HAS_RUST_CORE == False branches.
        """
        with patch.object(kid, "rust_loader") as mock_loader:
            mock_loader.HAS_RUST_CORE = False
            # 1. Init without Rust should raise
            with self.assertRaises(RuntimeError):
                KineticIdentity()

            # 2. Verify without Rust should raise
            with self.assertRaises(RuntimeError):
                KineticIdentity.verify_intent("pub", "payload", "sig")

            # 3. Keygen without Rust should raise
            with self.assertRaises(RuntimeError):
                KineticIdentity.generate_keypair()

            # 4. Sign without Rust should raise
            with self.assertRaises(RuntimeError):
                KineticIdentity.sign_intent_static("sk", "payload")

        # 5. Keygen WITH Rust (Static) - use actual rust loader
        if rust_loader.HAS_RUST_CORE:
            pk, sk = KineticIdentity.generate_keypair()
            self.assertIsNotNone(pk)

    def test_module_init_branches(self):
        # Covered by rust_loader tests
        pass


if __name__ == "__main__":
    unittest.main()
