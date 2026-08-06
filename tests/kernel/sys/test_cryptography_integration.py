# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for WarmLogic Cryptography with actual Rust core.

These tests use the real Rust core (no reload/mocking) to ensure
proper coverage tracking.
"""

import pytest

from warm_logic.kernel import rust_loader

# Skip all tests if Rust core not available
pytestmark = pytest.mark.skipif(
    not rust_loader.HAS_RUST_CORE,
    reason="Rust core not available",
)


class TestMLDSAIntegration:
    """Test MLDSA with actual Rust core."""

    def test_mldsa_init_with_rust(self):
        """MLDSA initializes with Rust core."""
        from warm_logic.kernel.sys.cryptography import MLDSA

        # Should not raise when Rust core available
        mldsa = MLDSA()
        assert mldsa.seed is None  # Default seed is None

    def test_mldsa_init_with_seed(self):
        """MLDSA accepts seed parameter."""
        from warm_logic.kernel.sys.cryptography import MLDSA

        mldsa = MLDSA(seed=b"test_seed_32_bytes_long_enough!!")
        assert mldsa.seed == b"test_seed_32_bytes_long_enough!!"

    def test_mldsa_generate_keypair(self):
        """MLDSA generates valid keypair."""
        from warm_logic.kernel.sys.cryptography import MLDSA

        mldsa = MLDSA()
        keypair = mldsa.generate_keypair()

        assert keypair.public_key is not None
        assert keypair.private_key is not None
        assert len(keypair.public_key) > 0
        assert len(keypair.private_key) > 0

    def test_mldsa_sign_and_verify(self):
        """MLDSA signs and verifies messages."""
        from warm_logic.kernel.sys.cryptography import MLDSA

        mldsa = MLDSA()
        keypair = mldsa.generate_keypair()

        message = "test message for signing"
        signature = mldsa.sign(message, keypair.private_key)

        assert signature is not None
        assert len(signature) > 0

        # Verify should succeed
        is_valid = mldsa.verify(message, signature, keypair.public_key)
        assert is_valid is True

    def test_mldsa_verify_wrong_message(self):
        """MLDSA verify fails with wrong message."""
        from warm_logic.kernel.sys.cryptography import MLDSA

        mldsa = MLDSA()
        keypair = mldsa.generate_keypair()

        signature = mldsa.sign("original message", keypair.private_key)

        # Verify with different message should fail
        is_valid = mldsa.verify("different message", signature, keypair.public_key)
        assert is_valid is False


class TestStateAttestorIntegration:
    """Test StateAttestor with actual Rust core."""

    def test_state_attestor_init(self):
        """StateAttestor initializes correctly."""
        from warm_logic.kernel.sys.cryptography import StateAttestor

        # Reset singleton state for clean test
        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None

        attestor = StateAttestor()
        assert attestor.mldsa is not None
        assert attestor._hardware is not None

    def test_get_instance_singleton(self):
        """get_instance returns singleton."""
        from warm_logic.kernel.sys.cryptography import StateAttestor

        # Reset singleton
        StateAttestor._instance = None
        StateAttestor._keypair = None

        instance1 = StateAttestor.get_instance()
        instance2 = StateAttestor.get_instance()

        assert instance1 is instance2

    def test_initialize_keypair(self):
        """initialize_keypair generates keypair."""
        from warm_logic.kernel.sys.cryptography import StateAttestor

        # Reset state
        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None

        attestor = StateAttestor()
        public_key = attestor.initialize_keypair(seal_to_hardware=False)

        assert public_key is not None
        assert len(public_key) > 0
        assert StateAttestor._keypair is not None

    def test_initialize_keypair_returns_cached(self):
        """initialize_keypair returns cached key on second call."""
        from warm_logic.kernel.sys.cryptography import StateAttestor

        # Reset state
        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None

        attestor = StateAttestor()
        key1 = attestor.initialize_keypair(seal_to_hardware=False)
        key2 = attestor.initialize_keypair(seal_to_hardware=False)

        assert key1 == key2

    def test_attest_state(self):
        """attest_state generates attestation."""
        from warm_logic.kernel.sys.cryptography import StateAttestor

        # Reset state
        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None

        attestor = StateAttestor()

        attestation = attestor.attest_state("abc123def456")

        assert "attestation" in attestation
        assert "signature" in attestation
        assert "public_key" in attestation
        assert attestation["attestation"]["state_hash"] == "abc123def456"
        assert attestation["attestation"]["algorithm"] == "ML-DSA-65"

    def test_sign_state(self):
        """sign_state returns signature."""
        from warm_logic.kernel.sys.cryptography import StateAttestor

        # Reset state
        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None

        attestor = StateAttestor()

        signature = attestor.sign_state("state_hash_123")

        assert signature is not None
        assert isinstance(signature, str)
        assert len(signature) > 0

    def test_verify_attestation(self):
        """verify_attestation validates signature."""
        from warm_logic.kernel.sys.cryptography import StateAttestor

        # Reset state
        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None

        attestor = StateAttestor()

        # Create attestation
        attestation = attestor.attest_state("verify_test_hash")

        # Verify it
        is_valid = attestor.verify_attestation(attestation)
        assert is_valid is True

    def test_get_private_key_without_init_raises(self):
        """_get_private_key raises when keypair not initialized."""
        from warm_logic.kernel.sys.cryptography import StateAttestor

        # Reset state
        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None

        attestor = StateAttestor()

        with pytest.raises(RuntimeError) as exc_info:
            attestor._get_private_key()

        assert "Keypair not initialized" in str(exc_info.value)


class TestHardwareEnclaveIntegration:
    """Test HardwareEnclave with actual Rust core."""

    def test_hardware_enclave_init(self):
        """HardwareEnclave initializes without error."""
        from warm_logic.kernel.sys.cryptography import HardwareEnclave

        # Should not raise - calls HardwareGuard internally
        enclave = HardwareEnclave()
        assert enclave is not None

    def test_get_hardware_uuid(self):
        """get_hardware_uuid returns UUID string."""
        from warm_logic.kernel.sys.cryptography import HardwareEnclave

        uuid = HardwareEnclave.get_hardware_uuid()
        assert uuid is not None
        assert isinstance(uuid, str)
        assert len(uuid) > 0

    def test_get_kinetic_seed(self):
        """get_kinetic_seed returns bytes."""
        from warm_logic.kernel.sys.cryptography import HardwareEnclave

        seed = HardwareEnclave.get_kinetic_seed()
        assert seed is not None
        assert isinstance(seed, bytes)
        assert len(seed) > 0

    def test_kinetic_sovereign_alias(self):
        """KineticSovereign is alias for HardwareEnclave."""
        from warm_logic.kernel.sys.cryptography import (
            HardwareEnclave,
            KineticSovereign,
        )

        assert KineticSovereign is HardwareEnclave


class TestPQCKeypairIntegration:
    """Test PQCKeypair with actual Rust core."""

    def test_pqc_keypair_generate(self):
        """PQCKeypair.generate() calls Rust core."""
        from warm_logic.kernel.sys.cryptography import PQCKeypair

        public_key, private_key = PQCKeypair.generate()

        assert public_key is not None
        assert private_key is not None
        assert len(public_key) > 0
        assert len(private_key) > 0
