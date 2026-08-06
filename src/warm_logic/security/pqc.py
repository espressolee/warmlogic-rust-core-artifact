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
Post-Quantum Cryptography Module.
FIPS 204 (ML-DSA-65) Implementation via Rust Core.

SECURITY POLICY: No fallback. Rust Core is MANDATORY.
"""

import logging

logger = logging.getLogger("SovereignSecurity")

# [P0] HARD FAILURE: Rust Core is mandatory for cryptographic operations
try:
    import warm_logic_rs

    logger.info("[Security] Rust Core Loaded. FIPS 204 (ML-DSA-65) Enabled.")
except ImportError as e:
    raise RuntimeError(
        "CRITICAL: Rust Core (warm_logic_rs) is required for cryptographic operations. "
        "Post-Quantum Security cannot be guaranteed without it. "
        "Run: cd rust_core && maturin develop --release --features 'python,std,persistence'"
    ) from e


class SovereignSecurity:
    """
    The Post-Quantum Shield.
    Wraps the FIPS 204 (ML-DSA-65) implementation from Rust.

    NO MOCK FALLBACK. Cryptographic operations require real implementation.
    """

    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """Generate ML-DSA-65 keypair (FIPS 204)."""
        result = warm_logic_rs.generate_keypair()
        return (str(result[0]), str(result[1]))

    @staticmethod
    def sign(private_key: str, message: str) -> str:
        """Sign message with ML-DSA-65 private key."""
        return str(warm_logic_rs.sign(private_key, message))

    @staticmethod
    def verify(public_key: str, message: str, signature: str) -> bool:
        """Verify ML-DSA-65 signature."""
        try:
            return bool(warm_logic_rs.verify(public_key, message, signature))
        except Exception as e:
            logger.error(f"[Security] Verification Error: {e}")
            return False


class KeyEncapsulation:
    """
    ML-KEM-768 Key Encapsulation Mechanism (FIPS 203).

    Status: PLANNED - Awaiting Rust Core implementation.

    Once implemented, this provides:
    - Key encapsulation for perfect forward secrecy
    - 192-bit post-quantum security (Level 3)
    - Ciphertext size: 1088 bytes
    - Shared secret size: 32 bytes

    P3xx Tracking: Requires fips203 crate vendoring in rust_core.
    """

    # Key sizes (NIST Level 3)
    PUBLIC_KEY_SIZE = 1184  # bytes
    PRIVATE_KEY_SIZE = 2400  # bytes
    CIPHERTEXT_SIZE = 1088  # bytes
    SHARED_SECRET_SIZE = 32  # bytes

    @staticmethod
    def is_available() -> bool:
        """Check if ML-KEM-768 is available in Rust Core."""
        return hasattr(warm_logic_rs, "kem_generate_keypair")

    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """
        Generate ML-KEM-768 keypair.

        Returns:
            (public_key_hex, private_key_hex)

        Raises:
            NotImplementedError: If Rust Core lacks ML-KEM support.
        """
        if not KeyEncapsulation.is_available():
            raise NotImplementedError(
                "ML-KEM-768 (FIPS 203) not yet implemented in Rust Core. "
                "P3xx: Requires fips203 crate integration."
            )
        result = warm_logic_rs.kem_generate_keypair()
        return (str(result[0]), str(result[1]))

    @staticmethod
    def encapsulate(public_key: str) -> tuple[str, str]:
        """
        Encapsulate a shared secret for the given public key.

        Args:
            public_key: Recipient's ML-KEM-768 public key (hex).

        Returns:
            (ciphertext_hex, shared_secret_hex)

        Raises:
            NotImplementedError: If Rust Core lacks ML-KEM support.
        """
        if not KeyEncapsulation.is_available():
            raise NotImplementedError(
                "ML-KEM-768 (FIPS 203) not yet implemented in Rust Core."
            )
        result = warm_logic_rs.kem_encapsulate(public_key)
        return (str(result[0]), str(result[1]))

    @staticmethod
    def decapsulate(private_key: str, ciphertext: str) -> str:
        """
        Decapsulate a shared secret using the private key.

        Args:
            private_key: ML-KEM-768 private key (hex).
            ciphertext: Ciphertext from encapsulate() (hex).

        Returns:
            shared_secret_hex

        Raises:
            NotImplementedError: If Rust Core lacks ML-KEM support.
        """
        if not KeyEncapsulation.is_available():
            raise NotImplementedError(
                "ML-KEM-768 (FIPS 203) not yet implemented in Rust Core."
            )
        return str(warm_logic_rs.kem_decapsulate(private_key, ciphertext))


class HybridEncryption:
    """
    Hybrid PQC Encryption combining ML-KEM-768 + AES-256-GCM.

    Status: PLANNED - Depends on KeyEncapsulation implementation.

    Pattern:
    1. Generate ephemeral ML-KEM keypair
    2. Encapsulate shared secret with recipient's public key
    3. Derive AES-256 key from shared secret via HKDF
    4. Encrypt payload with AES-256-GCM
    5. Return (ciphertext, nonce, kem_ciphertext)

    This provides both post-quantum security and authenticated encryption.
    """

    @staticmethod
    def is_available() -> bool:
        """Check if hybrid encryption is available."""
        return KeyEncapsulation.is_available()

    @staticmethod
    def encrypt(public_key: str, plaintext: bytes) -> dict:
        """
        Encrypt data using hybrid ML-KEM + AES-GCM scheme.

        Args:
            public_key: Recipient's ML-KEM-768 public key (hex).
            plaintext: Data to encrypt.

        Returns:
            {
                "kem_ciphertext": str,  # ML-KEM ciphertext (hex)
                "aes_ciphertext": str,  # AES-GCM ciphertext (hex)
                "nonce": str,           # AES-GCM nonce (hex)
                "tag": str,             # AES-GCM auth tag (hex)
            }

        Raises:
            NotImplementedError: If ML-KEM not available.
        """
        if not HybridEncryption.is_available():
            raise NotImplementedError(
                "Hybrid encryption requires ML-KEM-768 (FIPS 203) support."
            )
        result = warm_logic_rs.hybrid_encrypt(public_key, plaintext)
        return dict(result)

    @staticmethod
    def decrypt(private_key: str, encrypted: dict) -> bytes:
        """
        Decrypt data using hybrid ML-KEM + AES-GCM scheme.

        Args:
            private_key: ML-KEM-768 private key (hex).
            encrypted: Dict from encrypt().

        Returns:
            Decrypted plaintext bytes.

        Raises:
            NotImplementedError: If ML-KEM not available.
        """
        if not HybridEncryption.is_available():
            raise NotImplementedError(
                "Hybrid encryption requires ML-KEM-768 (FIPS 203) support."
            )
        return bytes(warm_logic_rs.hybrid_decrypt(private_key, encrypted))
