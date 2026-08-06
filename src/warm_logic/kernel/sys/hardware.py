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
import hashlib
import logging
import os

logger = logging.getLogger("Hardware")


class HardwareAttestor:
    """
    Physical Rooting.
    Extracts hardware-bound identifiers to anchor PQC identities in physical silicon.
    """

    @staticmethod
    def get_hardware_uuid() -> str:
        """Retrieves the system's unique hardware UUID via SovereignHAL."""
        from warm_logic.kernel.substrate.hardware import SovereignHAL

        try:
            return SovereignHAL().get_silicon_id()
        except Exception as e:
            logger.error(f"Hardware identification failed: {e}")
            raise RuntimeError("hardware attestation enforcement: Physical Hardware ID required.")

    @staticmethod
    def generate_attestation_packet() -> str:
        """Generates a hardware-bound attestation string for identity binding."""
        hw_uuid = HardwareAttestor.get_hardware_uuid()
        kernel_version = os.uname().release

        # In a real TPM implementation, this would involve a TPM_Quote signed by the AIK
        raw_token = f"WARM-HW-ROOT|{hw_uuid}|{kernel_version}"
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @staticmethod
    def verify_attestation(identity_hw_hash: str) -> bool:
        """Verifies if the current hardware matches the bound identity hash."""
        current_hash = HardwareAttestor.generate_attestation_packet()
        return current_hash == identity_hw_hash
