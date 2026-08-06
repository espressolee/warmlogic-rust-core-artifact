import logging
from typing import Optional, Tuple

import warm_logic_rs

logger = logging.getLogger("SovereignIdentity")


class SovereignIdentity:
    """
    Universal wrapper for WarmLogic PQC Identity (SDK Version).
    Unifies SDK 'Identity' with Kernel 'KineticIdentity' logic without kernel dependencies.
    """

    def __init__(self, keypair: Optional[Tuple[str, str]] = None):
        if keypair:
            self.public_key, self.private_key = keypair
        else:
            # Generate fresh PQC keypair using Rust
            try:
                self.public_key, self.private_key = warm_logic_rs.generate_keypair()
            except AttributeError:
                # Fallback for older bindings or direct module usage
                # If warm_logic_rs is the module, check if it has generate_keypair directly
                # or if we need to instantiate a class.
                # Assuming top-level function based on kinetic_id.py analysis
                raise ImportError(
                    "warm_logic_rs does not support generate_keypair. Check version."
                )

        self._id = self.public_key
        logger.info(f"Identity Initialized: {self._id[:16]}...")

    @property
    def id(self) -> str:
        """The public Kinetic Identifier (W-ID)."""
        return self._id

    def sign(self, message: str) -> str:
        """
        Signs a message string using ML-DSA-65.
        Returns hex-encoded signature.
        """
        return warm_logic_rs.sign(self.private_key, message)

    def verify(self, message: str, signature: str) -> bool:
        """
        Verifies a signature against this identity's public key.
        """
        return warm_logic_rs.verify(self._id, message, signature)

    def export_public(self) -> str:
        """Exports the public key for registry/mesh announcements."""
        return self._id

    def __repr__(self) -> str:
        return f"<SovereignIdentity id={self.id[:16]}...>"
