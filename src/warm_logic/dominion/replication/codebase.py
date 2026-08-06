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
import os
from typing import Any, Dict, Tuple


class SovereignCodebase:
    """
    Self-replication and integrity verification engine.
    Stores file hashes and content for tamper detection and auto-healing.
    """

    def __init__(self, store: Any) -> None:
        self.store = store
        self._files: Dict[str, Tuple[str, bytes]] = {}  # path -> (hash, content)

    def _hash_file(self, path: str) -> str:
        """Compute SHA256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def ingest(self, root_path: str) -> int:
        """
        Ingest all Python files from root_path and store their hashes and content.
        Returns the count of files ingested.
        """
        count = 0
        for root, _, files in os.walk(root_path):
            for fname in files:
                if fname.endswith(".py"):
                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, root_path)
                    with open(full_path, "rb") as f:
                        content = f.read()
                    file_hash = hashlib.sha256(content).hexdigest()
                    self._files[rel_path] = (file_hash, content)
                    count += 1
        return count

    def generate_manifest(self) -> str:
        """
        Generate a SHA256 hash of all stored file hashes (sorted by path).
        """
        manifest = hashlib.sha256()
        for path in sorted(self._files.keys()):
            file_hash, _ = self._files[path]
            manifest.update(f"{path}:{file_hash}\n".encode())
        return manifest.hexdigest()

    def verify_integrity(self, root_path: str) -> bool:
        """
        Verify that files on disk match their stored hashes.
        Returns False if any file has been tampered.
        """
        for rel_path, (stored_hash, _) in self._files.items():
            full_path = os.path.join(root_path, rel_path)
            if not os.path.exists(full_path):
                return False
            current_hash = self._hash_file(full_path)
            if current_hash != stored_hash:
                return False
        return True

    def auto_heal(self, root_path: str) -> int:
        """
        Restore tampered files from stored content.
        Returns the count of healed files.
        """
        healed_count = 0
        for rel_path, (stored_hash, original_content) in self._files.items():
            full_path = os.path.join(root_path, rel_path)
            if not os.path.exists(full_path):
                # File was deleted - restore it
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "wb") as f:
                    f.write(original_content)
                healed_count += 1
            else:
                current_hash = self._hash_file(full_path)
                if current_hash != stored_hash:
                    # File was tampered - restore original content
                    with open(full_path, "wb") as f:
                        f.write(original_content)
                    healed_count += 1
        return healed_count
