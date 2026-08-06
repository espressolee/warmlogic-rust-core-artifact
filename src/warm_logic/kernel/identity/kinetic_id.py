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
import logging
from typing import Optional, Tuple

# Centralized Rust Core Loader
from warm_logic.kernel import rust_loader

logger = logging.getLogger("KineticIdentity")


class KineticIdentity:
    """
    Kinetic Identity (W-ID)
    Provides cryptographic proof of ownership for kernel interactions.
    """

    def __init__(self, keypair: Optional[Tuple[str, str]] = None):
        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError(
                "CRITICAL: Rust Core missing. Kinetic Identity is disabled for hardware attestation enforcement."
            )

        if keypair:
            self.public_key, self.private_key = keypair
        else:
            rs = rust_loader.load_rust_core()
            self.public_key, self.private_key = rs.generate_keypair()

    def sign_intent(self, intent_payload: str) -> str:
        """
        Generates a Kinetic Proof (Signature) for a given intent using this instance's key.
        """
        return self.sign_intent_static(self.private_key, intent_payload)

    def save_sealed(self, path: str):
        """
        Seals the private key to the current hardware and saves to disk.
        """
        from warm_logic.kernel.sys.cryptography import HardwareEnclave

        pk_bytes = self.private_key.encode()
        sealed = HardwareEnclave.seal_to_silicon(pk_bytes)

        with open(path, "wb") as f:
            # We save public key in clear, private key sealed
            f.write(self.public_key.encode() + b"\n")
            f.write(sealed)
        logger.info(f" Kinetic Identity SEALED and saved to {path}")

    @classmethod
    def from_sealed_file(cls, path: str) -> "KineticIdentity":
        """
        Loads a sealed identity from disk, unsealing the private key.
        """
        from warm_logic.kernel.sys.cryptography import HardwareEnclave

        with open(path, "rb") as f:
            public_key = f.readline().decode().strip()
            sealed_sk = f.read()

        private_key = HardwareEnclave.unseal_from_silicon(sealed_sk).decode()
        return cls(keypair=(public_key, private_key))

    @staticmethod
    def generate_keypair() -> Tuple[str, str]:
        """
        Static access to Rust keygen.
        """
        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError("CRITICAL: Rust Core missing. Cannot generate keys.")
        rs = rust_loader.load_rust_core()
        val = rs.generate_keypair()
        return (str(val[0]), str(val[1]))

    @staticmethod
    def sign_intent_static(private_key: str, intent_payload: str) -> str:
        """
        Static access to Rust signing.
        """
        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError("CRITICAL: Rust Core missing. Cannot sign intent.")
        if not private_key:
            raise RuntimeError("Cannot sign without private key")
        rs = rust_loader.load_rust_core()
        return str(rs.sign(private_key, intent_payload))

    @staticmethod
    def verify_intent(public_key: str, intent_payload: str, signature: str) -> bool:
        """
        Verifies a Kinetic Proof.
        """
        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError("CRITICAL: Rust Core missing. Cannot verify intent.")

        rs = rust_loader.load_rust_core()
        return bool(rs.verify(public_key, intent_payload, signature))
