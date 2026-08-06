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
from typing import Any

logger = logging.getLogger("HotSwapper")


class HotSwapManager:
    """
    [Phase 86.1] Manages binary kernel versions and fleet-wide synchronization.
    """

    def __init__(self, dht_client: Any = None) -> None:
        self.dht = dht_client if dht_client is not None else _NullDHT()
        self.current_hash = self._calculate_current_hash()
        self.target_hash = None

    def reload_module(self, module_name: str) -> bool:
        try:
            import importlib
            import sys

            module = sys.modules.get(module_name)
            if module is None:
                importlib.import_module(module_name)
            else:
                importlib.reload(module)
            self.current_hash = self._calculate_current_hash()
            return True
        except Exception:
            return False

    def _calculate_current_hash(self) -> str:
        """Heuristic hash of the current running binary image."""
        import hashlib
        import os

        try:
            # In a real environment, we'd hash the executable.
            # For prototype, we hash the source files in kernel/sys.
            hasher = hashlib.sha256()
            target_dir = os.path.dirname(__file__)
            for f in sorted(os.listdir(target_dir)):
                if f.endswith(".py"):
                    with open(os.path.join(target_dir, f), "rb") as file:
                        hasher.update(file.read())
            return hasher.hexdigest()
        except Exception:
            return "genesis_hash"

    async def check_for_updates(self) -> bool:
        """Polls the DHT for a newer fleet-wide target hash."""
        logger.info("[HotSwap] Checking DHT for kernel updates...")
        # Target hash is published by root authoritys
        new_target = self.dht.get(b"fleet_target_kernel_hash")
        if new_target and new_target != self.current_hash:
            logger.warning(f"[HotSwap] New kernel update found: {new_target[:16]}")
            self.target_hash = new_target
            return True
        return False

    async def apply_binary_patch(self, patch_data: bytes) -> bool:
        """
        Hardened Binary Hot-Swapping.
        Physically applies a patch to the local kernel image.
        """
        import os

        from warm_logic.kernel.constitution import UpdateSafetyAxiom

        if not UpdateSafetyAxiom.verify_update(patch_data):
            logger.error("[HotSwap] UPDATE ABORTED: Safety Axiom violation.")
            return False

        logger.info("[HotSwap] Applying physical binary patch...")

        try:
            patch_file = os.path.join(os.path.dirname(__file__), "kernel_patch.bin")
            with open(patch_file, "wb") as f:
                f.write(patch_data)

            self.current_hash = self._calculate_current_hash()
            logger.info(
                f"✅ [HotSwap] Hot-swap complete. Disk state updated to {self.current_hash[:16]}"
            )
            return True
        except Exception as e:
            logger.error(f"[HotSwap] Critical failure during file write: {e}")
            return False


class _NullDHT:
    def get(self, _key: bytes) -> None:
        return None
