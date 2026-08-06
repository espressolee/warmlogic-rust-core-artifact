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

try:
    import warm_logic_rs

    RUST_CORE_TPM_AVAILABLE = (
        hasattr(warm_logic_rs, "tpm_available") and warm_logic_rs.tpm_available()
    )
except ImportError:
    RUST_CORE_TPM_AVAILABLE = False


logger = logging.getLogger("SovereignHAL")


class SovereignHAL:
    """
    Sovereign Hardware Abstraction Layer.
    Binds the kernel to Physical Silicon (TPM/Enclave).
    """

    def __init__(self):
        self.kinetic_seal_available = False
        try:
            # Check if we have hardware entropy available (macOS/Darwin RoT)
            available, info = warm_logic_rs.get_hardware_info()
            if available:
                self.kinetic_seal_available = True
                logger.info(
                    f"💎 [Hardware] KINETIC SEAL ACTIVE. Identity bound to: {info}"
                )
        except Exception:
            pass

        if not RUST_CORE_TPM_AVAILABLE and not self.kinetic_seal_available:
            logger.critical(
                "❌ [Hardware] TPM NOT DETECTED and KINETIC SEAL FAILED. Production Kernel requires physical silicon."
            )
            raise RuntimeError(
                "hardware attestation enforcement: Kernel cannot boot without hardware boundary."
            )

        if RUST_CORE_TPM_AVAILABLE:
            logger.info(
                "🛡️ [Hardware] REAL TPM 2.0 DETECTED. Kernel is binding to discrete Silicon."
            )

    def get_silicon_id(self) -> str:
        """Returns the immutable unique ID of the hardware."""
        try:
            # Derived from HardwareGuard / Rust Core
            return warm_logic_rs.get_hardware_uuid()
        except Exception as e:
            logger.error(f"[Hardware] Failed to retrieve Silicon ID: {e}")
            raise RuntimeError(
                "Hardware Integrity Compromised: Silicon ID Unreachable."
            )

    def read_pcr(self, index: int) -> str:
        """Reads a Platform Configuration Register (integrity measurement)."""
        try:
            # Real TPM read via Rust
            pcr_bytes = warm_logic_rs.tpm_read_pcr(index)
            return bytes(pcr_bytes).hex()
        except Exception as e:
            logger.error(f"[Hardware] TPM Read Failed: {e}")
            raise RuntimeError(
                f"Hardware Integrity Compromised: PCR[{index}] Read Failed."
            )

    def extend_pcr(self, index: int, value: str):
        """TPM_Extend: PCR[i] = Hash(PCR[i] || value)."""
        try:
            warm_logic_rs.tpm_extend_pcr(index, value)
            logger.debug(f"[Hardware] Extended PCR[{index}] with {value[:8]}...")
        except Exception as e:
            logger.error(f"[Hardware] TPM Extend Failed: {e}")
            raise RuntimeError(
                f"Hardware Integrity Compromised: PCR[{index}] Extend Failed."
            )

    def seal_data(self, data: bytes) -> bytes:
        """
        [Clone Defense] Encrypts data bound to the current Silicon ID.
        Uses real hardware attributes (IOKit UUID) to derive the key.
        """
        try:
            res = warm_logic_rs.tpm_seal(data)
            return bytes(res) if isinstance(res, list) else res
        except Exception as e:
            logger.error(f"[Hardware] Seal Failed: {e}")
            raise RuntimeError("Hardware Integrity Compromised: Seal Operation Failed.")

    def unseal_data(self, sealed_data: bytes) -> bytes:
        """Decrypts data ONLY if running on the same Silicon ID."""
        try:
            res = warm_logic_rs.tpm_unseal(sealed_data)
            return bytes(res) if isinstance(res, list) else res
        except Exception as e:
            logger.error(f"[Hardware] Unseal Failed: {e}")
            raise RuntimeError(f"Hardware Integrity Compromised: {e}")
