import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import real PQC implementation from Rust core
try:
    from warm_logic_rs import generate_keypair, sign, verify

    HAS_RUST_PQC = True
except ImportError:
    HAS_RUST_PQC = False
    logger.warning("Rust PQC not available - DilithiumSigner will raise errors")


class DilithiumSigner:
    """
    Implements ML-DSA-65 (Dilithium) signatures for Sovereign Kernel ticks.

    Axiom 03: Post-Quantum Resilience.
    All state transitions must be signed by a quantum-resistant key.

    Uses real ML-DSA-65 implementation via warm_logic_rs Rust bindings.
    """

    ALG_ID = "ML-DSA-65"

    def __init__(self, key_path: Optional[str] = None):
        if not HAS_RUST_PQC:
            raise RuntimeError(
                "PQC requires warm_logic_rs Rust core. "
                "Build with: cd rust_core && maturin develop"
            )
        self.pubkey, self.privkey = self._load_or_gen_keys(key_path)

    def _load_or_gen_keys(self, path: Optional[str]) -> Tuple[str, str]:
        # Generate real ML-DSA-65 keypair via Rust core
        # TODO: Add key persistence to path if specified
        pub, priv = generate_keypair()
        return pub, priv

    def sign(self, message: bytes) -> str:
        """
        Signs the message using the ML-DSA-65 private key.
        Returns hex-encoded signature with algorithm prefix.
        """
        msg_hex = message.hex() if isinstance(message, bytes) else message
        sig = sign(self.privkey, msg_hex)
        return f"{self.ALG_ID}:{sig}"

    def verify(self, message: bytes, signature: str, pubkey: str) -> bool:
        """
        Verifies a ML-DSA-65 signature against the public key.
        """
        if not signature.startswith(self.ALG_ID + ":"):
            return False

        sig_hex = signature[len(self.ALG_ID) + 1 :]
        msg_hex = message.hex() if isinstance(message, bytes) else message
        return verify(pubkey, msg_hex, sig_hex)

    def get_public_key_hex(self) -> str:
        return self.pubkey
