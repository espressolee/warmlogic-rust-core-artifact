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
import io
import logging
import os
import tarfile
from typing import Optional, Tuple

from warm_logic.security.pqc import SovereignSecurity

logger = logging.getLogger("SovereignBundler")


class LogosBundler:
    """
    Utility to package the codebase into a signed bundle for mesh propagation.
    """

    def __init__(self, root_path: str = "."):
        self.root_path = os.path.abspath(root_path)
        self.ignore_dirs = {
            ".git",
            ".venv",
            "__pycache__",
            ".gemini",
            "node_modules",
            ".pytest_cache",
            "sovereign_db",
        }

    def create_bundle(self) -> Tuple[bytes, str]:
        """
        Creates a tar.gz bundle of the codebase and returns (bytes, manifest_hash).
        """
        buf = io.BytesIO()
        hasher = hashlib.sha256()

        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for root, dirs, files in os.walk(self.root_path):
                # Prune ignored directories
                dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

                for file in files:
                    if not file.endswith((".py", ".pyi", ".rs", ".toml", ".md")):
                        continue

                    full_path = os.path.join(root, file)
                    if not os.path.exists(full_path):
                        continue

                    rel_path = os.path.relpath(full_path, self.root_path)
                    if not rel_path or rel_path == ".":
                        rel_path = file

                    # Add to tar
                    tar.add(full_path, arcname=rel_path)

                    # Add to hash (path + content)
                    try:
                        with open(full_path, "rb") as f:
                            content = f.read()
                            hasher.update(rel_path.encode())
                            hasher.update(content)
                    except (FileNotFoundError, PermissionError) as e:
                        logger.warning(f"[kernel] Skipping file {full_path}: {e}")
                        continue

        bundle_bytes = buf.getvalue()
        manifest_hash = hasher.hexdigest()

        logger.info(
            f"📦 [kernel] Bundle created. Size: {len(bundle_bytes)} bytes. Hash: {manifest_hash}"
        )
        return bundle_bytes, manifest_hash

    def _safe_extract_filter(
        self, member: tarfile.TarInfo, dest_path: str
    ) -> Optional[tarfile.TarInfo]:
        """Filter to prevent path traversal attacks (CVE-2007-4559)."""
        # Reject absolute paths
        if member.name.startswith("/") or member.name.startswith("\\"):
            logger.warning(f"Rejected absolute path in tarball: {member.name}")
            return None
        # Reject path traversal
        if ".." in member.name:
            logger.warning(f"Rejected path traversal in tarball: {member.name}")
            return None
        # Reject symbolic links pointing outside
        if member.issym() or member.islnk():
            logger.warning(f"Rejected symlink in tarball: {member.name}")
            return None
        return member

    def unpack_bundle(self, bundle_bytes: bytes, target_dir: str):
        """
        Unpacks a bundle to a target directory with path traversal protection.
        """
        buf = io.BytesIO(bundle_bytes)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            # Use filter for Python 3.12+ or manual filtering for older versions
            safe_members = [
                m
                for m in tar.getmembers()
                if self._safe_extract_filter(m, target_dir) is not None
            ]
            try:
                tar.extractall(  # nosec B202
                    path=target_dir, members=safe_members, filter="data"
                )
            except TypeError:
                tar.extractall(path=target_dir, members=safe_members)  # nosec B202
        logger.info(f"[kernel] Bundle unpacked to {target_dir}")

    def sign_bundle(self, private_key: str, manifest_hash: str) -> str:
        """
        Signs the manifest hash with the node's private key.
        """
        signature = SovereignSecurity.sign(private_key, manifest_hash)
        logger.info(f"[kernel] Bundle signed. Signature: {signature[:16]}...")
        return signature

    def verify_bundle(
        self, public_key: str, manifest_hash: str, signature: str
    ) -> bool:
        """
        Verifies the bundle signature against the public key.
        """
        is_valid = SovereignSecurity.verify(public_key, manifest_hash, signature)
        if is_valid:
            logger.info(f"[kernel] Signature VERIFIED for {manifest_hash}")
        else:
            logger.error(f"[kernel] Signature INVALID for {manifest_hash}")
        return is_valid
