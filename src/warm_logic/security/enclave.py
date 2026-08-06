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
from typing import Any

logger = logging.getLogger("SovereignEnclave")


class HardwareEnclave:
    """
    [M] The Silicon Shield.
    Anchors PQC identities in the hardware enclave.
    Prevents raw private keys from touching main memory.
    """

    def __init__(self, hal: Any = None):
        from warm_logic.kernel.substrate.hardware import SovereignHAL

        self._hal = hal or SovereignHAL()
        self._sealed_keys: dict[str, bytes] = {}  # key_tag -> encrypted_bytes
        self._enclave_active: bool = True  # Track if hardware enclave is active

    def seal_identity(self, node_id: str, private_key: Any) -> bool:
        """
        Seals the private key into hardware-bound storage.
        """
        logger.info(f"[Enclave] Sealing identity for node '{node_id}'...")
        key_bytes = (
            private_key.encode() if isinstance(private_key, str) else private_key
        )
        sealed = self._hal.seal_data(key_bytes)
        self._sealed_keys[node_id] = sealed
        return True

    def hardware_sign(self, node_id: str, message: str) -> str:
        """
        Signs a message within the hardware boundary.
        The raw key is NEVER returned to the caller.
        """
        if node_id not in self._sealed_keys:
            raise KeyError(f"No identity sealed for {node_id}")

        logger.info(f"[Enclave] Hardware-accelerated PQC signing for '{node_id}'")
        # In M, this would call warm_logic_rs.enclave_sign(...)
        # For now, we simulate the non-extractability
        return f"ENCLAVE_SIG({node_id})_{hashlib.sha256(message.encode()).hexdigest()}"

    def is_hardware_backed(self) -> bool:
        return bool(self._enclave_active)
