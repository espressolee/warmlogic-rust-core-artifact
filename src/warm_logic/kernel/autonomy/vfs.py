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
from typing import Dict, List

logger = logging.getLogger("SovereignVFS")


class SovereignVFS:
    """
    [M] The Containment Sphere.
    A root-jailed virtual filesystem that enforces Martial Law on IO.
    Tracks file hashes in a local Merkle-like structure.
    """

    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)
        self._registry: Dict[str, str] = {}  # rel_path -> hash

    def _safe_path(self, path: str) -> str:
        """
        Ensures the path is within the root_path.
        """
        abs_path = os.path.abspath(os.path.join(self.root_path, path))
        if not abs_path.startswith(self.root_path):
            logger.critical(
                f"🛑 [VFS] ACCESS DENIED: Path traversal attempt to '{path}'"
            )
            raise PermissionError("Path traversal violation")
        return abs_path

    def read_text(self, path: str) -> str:
        safe_path = self._safe_path(path)
        with open(safe_path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
            self._update_registry(path, content)
            return content

    def write_text(self, path: str, content: str):
        safe_path = self._safe_path(path)
        parent = os.path.dirname(safe_path)
        os.makedirs(parent, exist_ok=True)

        with open(safe_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)

        self._update_registry(path, content)
        logger.info(f"[VFS] Write-Through successful: {path}")

    def _update_registry(self, path: str, content: str):
        rel_path = os.path.relpath(self._safe_path(path), self.root_path)
        h = hashlib.sha256(content.encode()).hexdigest()
        self._registry[rel_path] = h

    def get_merkle_root(self) -> str:
        """
        Computes a simple aggregate hash of the entire registry.
        """
        sorted_keys = sorted(self._registry.keys())
        combined = "".join(f"{k}:{self._registry[k]}" for k in sorted_keys)
        return hashlib.sha256(combined.encode()).hexdigest()

    def exists(self, path: str) -> bool:
        try:
            return os.path.exists(self._safe_path(path))
        except PermissionError:
            return False

    def list_dir(self, path: str = ".") -> List[str]:
        safe_path = self._safe_path(path)
        return os.listdir(safe_path)
