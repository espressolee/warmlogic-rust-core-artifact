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
from dataclasses import dataclass
from typing import Any, Dict, Optional

from warm_logic.kernel.hardware.confidential import HardwareGuard

logger = logging.getLogger("KernelCrypt")


@dataclass
class PQCKeypair:
    public_key: str
    private_key: str
    algorithm: str = "ML-DSA-65"

    @staticmethod
    def generate() -> tuple[str, str]:
        """
        Delegates to Rust Core (FIPS-204).
        Returns (public_key_hex, private_key_hex).
        """
        from warm_logic.kernel import rust_loader

        try:
            rs = rust_loader.load_rust_core()
            val = rs.PQCKeypair.generate()
            return (str(val[0]), str(val[1]))
        except Exception as e:
            raise RuntimeError(f"Rust Core Generation Failed: {e}")


class MLDSA:
    def __init__(self, seed: Optional[bytes] = None) -> None:
        self.seed = seed
        from warm_logic.kernel import rust_loader

        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError(
                "CRITICAL: Rust Core missing. MLDSA (PQC) operations are disabled."
            )

    def generate_keypair(self) -> PQCKeypair:
        from warm_logic.kernel import rust_loader

        try:
            rs = rust_loader.load_rust_core()
            pk_hex, sk_hex = rs.PQCKeypair.generate()
            return PQCKeypair(str(pk_hex), str(sk_hex))
        except Exception as e:
            raise RuntimeError(f"MLDSA KeyGen Failed via Core: {e}")

    def sign(self, message: str, private_key: str) -> str:
        from warm_logic.kernel import rust_loader

        try:
            rs = rust_loader.load_rust_core()
            return str(rs.MLDSA.sign(private_key, message))
        except Exception as e:
            raise RuntimeError(f"MLDSA Signing Failed via Core: {e}")

    def verify(self, message: str, signature: str, public_key: str) -> bool:
        from warm_logic.kernel import rust_loader

        try:
            rs = rust_loader.load_rust_core()
            return bool(rs.MLDSA.verify(public_key, message, signature))
        except Exception as e:
            logger.error(f"MLDSA Verification Error: {e}")
            return False


class StateAttestor:
    """
    Hardware-bound PQC State Attestation.

    Keys are sealed to silicon using HardwareEnclave, ensuring that
    state signatures are only valid on the originating hardware.
    """

    _instance: Optional["StateAttestor"] = None
    _keypair: Optional[PQCKeypair] = None
    _sealed_private_key: Optional[bytes] = None

    def __init__(self) -> None:
        self.mldsa = MLDSA()
        self._hardware = HardwareGuard

    @classmethod
    def get_instance(cls) -> "StateAttestor":
        """Singleton pattern for consistent key usage."""
        if cls._instance is None:
            cls._instance = StateAttestor()
        return cls._instance

    def initialize_keypair(self, seal_to_hardware: bool = True) -> str:
        """
        Initialize or load the hardware-bound PQC keypair.

        Args:
            seal_to_hardware: If True, seals private key to silicon.

        Returns:
            Public key hex string.
        """
        if StateAttestor._keypair is not None:
            return StateAttestor._keypair.public_key

        # Generate new PQC keypair via Rust Core
        keypair = self.mldsa.generate_keypair()
        StateAttestor._keypair = keypair

        if seal_to_hardware:  # pragma: no cover - requires hardware
            try:
                # Seal private key to hardware
                private_key_bytes = bytes.fromhex(keypair.private_key)
                StateAttestor._sealed_private_key = HardwareEnclave.seal_to_silicon(
                    private_key_bytes
                )
                logger.info("STATE_ATTESTOR: Private key sealed to silicon")
            except Exception as e:
                # In development mode, allow unsealed keys with warning
                logger.warning(f"STATE_ATTESTOR: Hardware sealing unavailable: {e}")
                StateAttestor._sealed_private_key = None

        return keypair.public_key

    def _get_private_key(self) -> str:
        """Retrieve private key, unsealing from hardware if necessary."""
        if StateAttestor._keypair is None:
            raise RuntimeError(
                "STATE_ATTESTOR: Keypair not initialized. Call initialize_keypair() first."
            )

        if (
            StateAttestor._sealed_private_key is not None
        ):  # pragma: no cover - hardware path
            try:
                # Unseal from hardware - fails if hardware mismatch
                unsealed = HardwareEnclave.unseal_from_silicon(
                    StateAttestor._sealed_private_key
                )
                return unsealed.hex()
            except Exception as e:
                logger.error(f"STATE_ATTESTOR: Hardware unseal failed: {e}")
                raise RuntimeError(f"SILICON_MISMATCH: Cannot unseal private key: {e}")

        # Fallback: use in-memory key (development mode)
        return StateAttestor._keypair.private_key

    def attest_state(self, state_hash: str) -> Dict[str, Any]:
        """
        Generate a hardware-attested state certification.

        Args:
            state_hash: SHA3-256 hash of the kernel state.

        Returns:
            Attestation dict containing signature, hardware report, and metadata.
        """
        import time

        # Ensure keypair is initialized
        if StateAttestor._keypair is None:
            self.initialize_keypair()

        # Get hardware attestation
        hw_report = self._hardware.get_hardware_report()

        # Construct attestation payload
        attestation_payload = {
            "state_hash": state_hash,
            "timestamp": int(time.time()),
            "hardware_id": hw_report.pcr_hash,
            "era": 3000,
            "algorithm": "ML-DSA-65",
        }

        import json

        payload_str = json.dumps(attestation_payload, sort_keys=True)

        # Sign with hardware-bound PQC key
        private_key = self._get_private_key()
        if StateAttestor._keypair is None:
            raise RuntimeError("Keypair not initialized after _get_private_key()")
        signature = self.mldsa.sign(payload_str, private_key)

        return {
            "attestation": attestation_payload,
            "signature": signature,
            "public_key": StateAttestor._keypair.public_key,
            "hardware_report": {
                "pcr_hash": hw_report.pcr_hash,
                "quote": hw_report.quote,
                "reality_score": getattr(hw_report, "reality_score", 1.0),
            },
        }

    def sign_state(self, state_hash: str) -> str:
        """
        Sign a state hash with the hardware-bound PQC key.

        Args:
            state_hash: SHA3-256 hash of the kernel state.

        Returns:
            ML-DSA-65 signature hex string.
        """
        if StateAttestor._keypair is None:
            self.initialize_keypair()

        private_key = self._get_private_key()
        return self.mldsa.sign(state_hash, private_key)

    def verify_attestation(self, attestation: Dict[str, Any]) -> bool:
        """
        Verify a state attestation signature.

        Args:
            attestation: Attestation dict from attest_state().

        Returns:
            True if signature is valid.
        """
        import json

        payload_str = json.dumps(attestation["attestation"], sort_keys=True)
        return self.mldsa.verify(
            payload_str,
            attestation["signature"],
            attestation["public_key"],
        )


class HardwareEnclave:
    """
    Secure Hardware Enclave interface.
    """

    def __init__(self) -> None:
        # Enforce hardware lock on initialization
        HardwareGuard.get_hardware_report()

    @staticmethod
    def get_hardware_uuid() -> str:
        """
        Retrieves the hardware-bound PCR hash from the attestation report.
        """
        report = HardwareGuard.get_hardware_report()
        return report.pcr_hash

    @staticmethod
    def get_kinetic_seed() -> bytes:
        from warm_logic.kernel import rust_loader

        try:
            rs = rust_loader.load_rust_core()
            sealed, _proof = rs.HardwareEntropy.derive_seed()
            return bytes.fromhex(sealed)
        except Exception as e:
            raise RuntimeError(f"Kinetic Seed derivation failed via Core: {e}")

    @staticmethod
    def seal_to_silicon(data: bytes) -> bytes:
        """
        Explicitly seal data to the host silicon.
        """
        from warm_logic.kernel import rust_loader

        rs = rust_loader.load_rust_core()
        try:
            result: bytes = rs.HardwareRealityBinder.seal_to_silicon(data)
            return result
        except Exception as e:
            logger.error(f"SILICON_SEAL_FAILED: {e}")
            raise

    @staticmethod
    def unseal_from_silicon(sealed_data: bytes) -> bytes:
        """
        Unseal silicon-bound data. Fails if hardware mismatched.
        """
        from warm_logic.kernel import rust_loader

        rs = rust_loader.load_rust_core()
        try:
            result: bytes = rs.HardwareRealityBinder.unseal_from_silicon(sealed_data)
            return result
        except Exception as e:
            logger.error(f"SILICON_UNSEAL_FAILED: {e}")
            raise

    @staticmethod
    def bind_genesis() -> str:
        """
        Signs the genesis state using the hardware-bound attestation quote.
        """
        report = HardwareGuard.get_hardware_report()
        success, msg = HardwareGuard.verify_system_integrity()
        if success:
            import hashlib

            return hashlib.sha256(report.quote.encode()).hexdigest()
        raise RuntimeError(f"Genesis Binding: Attestation Failed: {msg}")


# Reality Alignment
KineticSovereign = HardwareEnclave


class QuantumEnclave:
    """
    DEPRECATED: Subject to ground truth Protocol deletion.
    Use HardwareEnclave for all new logic.
    """

    def __init__(self) -> None:
        raise RuntimeError(
            "QuantumEnclave has been decommissioned. Use HardwareEnclave."
        )
