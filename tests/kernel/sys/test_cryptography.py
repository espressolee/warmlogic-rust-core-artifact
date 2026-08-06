# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic Cryptography module."""

from unittest.mock import MagicMock, patch

import pytest


class TestPQCKeypair:
    """Test PQCKeypair dataclass."""

    def test_keypair_fields(self):
        """PQCKeypair has expected fields."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            from warm_logic.kernel.sys.cryptography import PQCKeypair

        keypair = PQCKeypair(public_key="pub123", private_key="priv456")
        assert keypair.public_key == "pub123"
        assert keypair.private_key == "priv456"
        assert keypair.algorithm == "ML-DSA-65"

    def test_keypair_custom_algorithm(self):
        """PQCKeypair accepts custom algorithm."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            from warm_logic.kernel.sys.cryptography import PQCKeypair

        keypair = PQCKeypair(
            public_key="pub", private_key="priv", algorithm="CUSTOM-ALG"
        )
        assert keypair.algorithm == "CUSTOM-ALG"

    def test_generate_success(self):
        """PQCKeypair.generate() calls Rust core."""
        mock_rs = MagicMock()
        mock_rs.PQCKeypair.generate.return_value = ("public_hex", "private_hex")

        with patch(
            "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
        ):
            from warm_logic.kernel.sys.cryptography import PQCKeypair

            result = PQCKeypair.generate()

        assert result == ("public_hex", "private_hex")

    def test_generate_failure(self):
        """PQCKeypair.generate() raises on Rust error."""
        with patch(
            "warm_logic.kernel.rust_loader.load_rust_core",
            side_effect=Exception("Rust error"),
        ):
            from warm_logic.kernel.sys.cryptography import PQCKeypair

            with pytest.raises(RuntimeError) as exc_info:
                PQCKeypair.generate()

            assert "Rust Core Generation Failed" in str(exc_info.value)


class TestMLDSA:
    """Test MLDSA class."""

    def test_init_without_rust_raises(self):
        """MLDSA raises when Rust core not available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            from importlib import reload

            import warm_logic.kernel.sys.cryptography as crypto_mod

            reload(crypto_mod)

            with pytest.raises(RuntimeError) as exc_info:
                crypto_mod.MLDSA()

            assert "Rust Core missing" in str(exc_info.value)

    def test_init_with_rust_succeeds(self):
        """MLDSA initializes when Rust core available."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            from importlib import reload

            import warm_logic.kernel.sys.cryptography as crypto_mod

            reload(crypto_mod)

            mldsa = crypto_mod.MLDSA()
            assert mldsa.seed is None

    def test_init_with_seed(self):
        """MLDSA accepts optional seed."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            from importlib import reload

            import warm_logic.kernel.sys.cryptography as crypto_mod

            reload(crypto_mod)

            mldsa = crypto_mod.MLDSA(seed=b"test_seed")
            assert mldsa.seed == b"test_seed"

    def test_generate_keypair_success(self):
        """generate_keypair() returns PQCKeypair."""
        mock_rs = MagicMock()
        mock_rs.PQCKeypair.generate.return_value = ("pub_key", "priv_key")

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                mldsa = crypto_mod.MLDSA()
                keypair = mldsa.generate_keypair()

                assert keypair.public_key == "pub_key"
                assert keypair.private_key == "priv_key"

    def test_generate_keypair_failure(self):
        """generate_keypair() raises on Rust error."""
        mock_rs = MagicMock()
        mock_rs.PQCKeypair.generate.side_effect = Exception("KeyGen error")

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                mldsa = crypto_mod.MLDSA()

                with pytest.raises(RuntimeError) as exc_info:
                    mldsa.generate_keypair()

                assert "MLDSA KeyGen Failed" in str(exc_info.value)

    def test_sign_success(self):
        """sign() returns signature from Rust."""
        mock_rs = MagicMock()
        mock_rs.MLDSA.sign.return_value = "signature_hex"

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                mldsa = crypto_mod.MLDSA()
                sig = mldsa.sign("message", "private_key")

                assert sig == "signature_hex"
                mock_rs.MLDSA.sign.assert_called_once_with("private_key", "message")

    def test_sign_failure(self):
        """sign() raises on Rust error."""
        mock_rs = MagicMock()
        mock_rs.MLDSA.sign.side_effect = Exception("Signing error")

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                mldsa = crypto_mod.MLDSA()

                with pytest.raises(RuntimeError) as exc_info:
                    mldsa.sign("msg", "key")

                assert "MLDSA Signing Failed" in str(exc_info.value)

    def test_verify_success_true(self):
        """verify() returns True for valid signature."""
        mock_rs = MagicMock()
        mock_rs.MLDSA.verify.return_value = True

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                mldsa = crypto_mod.MLDSA()
                result = mldsa.verify("message", "signature", "public_key")

                assert result is True

    def test_verify_success_false(self):
        """verify() returns False for invalid signature."""
        mock_rs = MagicMock()
        mock_rs.MLDSA.verify.return_value = False

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                mldsa = crypto_mod.MLDSA()
                result = mldsa.verify("message", "bad_sig", "public_key")

                assert result is False

    def test_verify_error_returns_false(self):
        """verify() returns False on Rust error."""
        mock_rs = MagicMock()
        mock_rs.MLDSA.verify.side_effect = Exception("Verify error")

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                mldsa = crypto_mod.MLDSA()
                result = mldsa.verify("msg", "sig", "key")

                assert result is False


class TestStateAttestor:
    """Test StateAttestor class."""

    def test_attest_state_returns_attestation(self):
        """attest_state() returns attestation dict with signature."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            from importlib import reload

            import warm_logic.kernel.sys.cryptography as crypto_mod

            reload(crypto_mod)

            attestor = crypto_mod.StateAttestor()

            result = attestor.attest_state("hash123")

            assert "attestation" in result
            assert "signature" in result
            assert "public_key" in result
            assert result["attestation"]["state_hash"] == "hash123"

    def test_sign_state_returns_signature(self):
        """sign_state() returns signature string."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            from importlib import reload

            import warm_logic.kernel.sys.cryptography as crypto_mod

            reload(crypto_mod)

            attestor = crypto_mod.StateAttestor()

            result = attestor.sign_state("hash123")

            # sign_state returns a hex signature string
            assert isinstance(result, str)
            assert len(result) > 0


class TestHardwareEnclave:
    """Test HardwareEnclave class."""

    def test_init_calls_hardware_guard(self):
        """HardwareEnclave init calls HardwareGuard."""
        mock_report = MagicMock()

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                return_value=mock_report,
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                enclave = crypto_mod.HardwareEnclave()
                # Should not raise

    def test_get_hardware_uuid(self):
        """get_hardware_uuid() returns PCR hash."""
        mock_report = MagicMock()
        mock_report.pcr_hash = "pcr_hash_value"

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                return_value=mock_report,
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                uuid = crypto_mod.HardwareEnclave.get_hardware_uuid()
                assert uuid == "pcr_hash_value"

    def test_get_kinetic_seed_success(self):
        """get_kinetic_seed() returns derived seed."""
        mock_rs = MagicMock()
        # Return hex string for seed
        mock_rs.HardwareEntropy.derive_seed.return_value = ("deadbeef", "proof")
        mock_report = MagicMock()

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                with patch(
                    "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                    return_value=mock_report,
                ):
                    from importlib import reload

                    import warm_logic.kernel.sys.cryptography as crypto_mod

                    reload(crypto_mod)

                    seed = crypto_mod.HardwareEnclave.get_kinetic_seed()
                    assert seed == b"\xde\xad\xbe\xef"

    def test_get_kinetic_seed_failure(self):
        """get_kinetic_seed() raises on error."""
        mock_rs = MagicMock()
        mock_rs.HardwareEntropy.derive_seed.side_effect = Exception("Entropy error")
        mock_report = MagicMock()

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                with patch(
                    "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                    return_value=mock_report,
                ):
                    from importlib import reload

                    import warm_logic.kernel.sys.cryptography as crypto_mod

                    reload(crypto_mod)

                    with pytest.raises(RuntimeError) as exc_info:
                        crypto_mod.HardwareEnclave.get_kinetic_seed()

                    assert "Kinetic Seed derivation failed" in str(exc_info.value)

    def test_seal_to_silicon_success(self):
        """seal_to_silicon() returns sealed data."""
        mock_rs = MagicMock()
        mock_rs.HardwareRealityBinder.seal_to_silicon.return_value = b"sealed"
        mock_report = MagicMock()

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                with patch(
                    "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                    return_value=mock_report,
                ):
                    from importlib import reload

                    import warm_logic.kernel.sys.cryptography as crypto_mod

                    reload(crypto_mod)

                    result = crypto_mod.HardwareEnclave.seal_to_silicon(b"data")
                    assert result == b"sealed"

    def test_seal_to_silicon_failure(self):
        """seal_to_silicon() raises on error."""
        mock_rs = MagicMock()
        mock_rs.HardwareRealityBinder.seal_to_silicon.side_effect = Exception(
            "Seal error"
        )
        mock_report = MagicMock()

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                with patch(
                    "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                    return_value=mock_report,
                ):
                    from importlib import reload

                    import warm_logic.kernel.sys.cryptography as crypto_mod

                    reload(crypto_mod)

                    with pytest.raises(Exception):
                        crypto_mod.HardwareEnclave.seal_to_silicon(b"data")

    def test_unseal_from_silicon_success(self):
        """unseal_from_silicon() returns unsealed data."""
        mock_rs = MagicMock()
        mock_rs.HardwareRealityBinder.unseal_from_silicon.return_value = b"original"
        mock_report = MagicMock()

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                with patch(
                    "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                    return_value=mock_report,
                ):
                    from importlib import reload

                    import warm_logic.kernel.sys.cryptography as crypto_mod

                    reload(crypto_mod)

                    result = crypto_mod.HardwareEnclave.unseal_from_silicon(b"sealed")
                    assert result == b"original"

    def test_unseal_from_silicon_failure(self):
        """unseal_from_silicon() raises on error."""
        mock_rs = MagicMock()
        mock_rs.HardwareRealityBinder.unseal_from_silicon.side_effect = Exception(
            "Unseal error"
        )
        mock_report = MagicMock()

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                with patch(
                    "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                    return_value=mock_report,
                ):
                    from importlib import reload

                    import warm_logic.kernel.sys.cryptography as crypto_mod

                    reload(crypto_mod)

                    with pytest.raises(Exception):
                        crypto_mod.HardwareEnclave.unseal_from_silicon(b"sealed")

    def test_bind_genesis_success(self):
        """bind_genesis() returns genesis hash on success."""
        mock_report = MagicMock()
        mock_report.quote = "attestation_quote"

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                return_value=mock_report,
            ):
                with patch(
                    "warm_logic.kernel.hardware.confidential.HardwareGuard.verify_system_integrity",
                    return_value=(True, "OK"),
                ):
                    from importlib import reload

                    import warm_logic.kernel.sys.cryptography as crypto_mod

                    reload(crypto_mod)

                    result = crypto_mod.HardwareEnclave.bind_genesis()
                    # Should return SHA256 of quote
                    import hashlib

                    expected = hashlib.sha256(b"attestation_quote").hexdigest()
                    assert result == expected

    def test_bind_genesis_failure(self):
        """bind_genesis() raises on attestation failure."""
        mock_report = MagicMock()
        mock_report.quote = "quote"

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                return_value=mock_report,
            ):
                with patch(
                    "warm_logic.kernel.hardware.confidential.HardwareGuard.verify_system_integrity",
                    return_value=(False, "Integrity check failed"),
                ):
                    from importlib import reload

                    import warm_logic.kernel.sys.cryptography as crypto_mod

                    reload(crypto_mod)

                    with pytest.raises(RuntimeError) as exc_info:
                        crypto_mod.HardwareEnclave.bind_genesis()

                    assert "Attestation Failed" in str(exc_info.value)


class TestQuantumEnclave:
    """Test QuantumEnclave class."""

    def test_init_raises(self):
        """QuantumEnclave init always raises."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                return_value=MagicMock(),
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                with pytest.raises(RuntimeError) as exc_info:
                    crypto_mod.QuantumEnclave()

                assert "decommissioned" in str(exc_info.value)


class TestKineticSovereign:
    """Test KineticSovereign alias."""

    def test_kinetic_sovereign_is_hardware_enclave(self):
        """KineticSovereign is alias for HardwareEnclave."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.hardware.confidential.HardwareGuard.get_hardware_report",
                return_value=MagicMock(),
            ):
                from importlib import reload

                import warm_logic.kernel.sys.cryptography as crypto_mod

                reload(crypto_mod)

                assert crypto_mod.KineticSovereign is crypto_mod.HardwareEnclave
