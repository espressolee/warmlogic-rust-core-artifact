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
"""
Sovereign Provenance
Enforces strict runtime code integrity.
"If it isn't signed, it doesn't run."
"""

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional, Tuple, Union

# --- Genetic Integrity (Self-Replication) ---
from warm_logic.dominion.replication.codebase import SovereignCodebase

# [/Phase G] PQC Bootloader Upgrade
from warm_logic.kernel.sys.cryptography import MLDSA
from warm_logic.kernel.sys.persistence import SovereignStore

from .ledger import GlobalLedger  # expose Ledger

# Hardcoded paths relative to this file
# warm_logic/kernel/provenance/__init__.py -> provenance -> kernel -> warm_logic -> Root (src)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
MANIFEST_PATH = ROOT_DIR / "data" / "provenance" / "manifest.json"
PUB_KEY_PATH = ROOT_DIR / "data" / "provenance" / "sovereign_pub.dat"


class CodeIntegrityGuard:
    def __init__(self, strict: bool = True) -> None:
        self.strict = strict
        self.verified = False

    def _hash_file(self, filepath: Path) -> Optional[str]:
        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            return None

    def enforce(self) -> None:
        """
        Scans critical code paths and verifies against manifest.
        Raises SystemExit if integrity is compromised.
        """
        print(" SOVEREIGN PROVENANCE: Initiating Integrity Check...")

        if not MANIFEST_PATH.exists():
            msg = "❌ CRITICAL: No Provenance Manifest found. System is UNTRUSTED."
            print(msg)
            if self.strict:
                sys.exit(1)
            return

        try:
            with open(MANIFEST_PATH, "r") as f:
                manifest = json.load(f)
        except json.JSONDecodeError:
            print("CRITICAL: Manifest corrupted.")
            sys.exit(1)

        # 1. Verify Signature
        if not self._verify_signature(manifest):
            print("CRITICAL: Manifest signature INVALID. Trust chain broken.")
            sys.exit(1)

        # 2. Verify File Hashes
        errors = 0
        file_map = manifest["files"]

        # Check all files listed in manifest
        for rel_path_str, expected_hash in file_map.items():
            full_path = ROOT_DIR / rel_path_str
            actual_hash = self._hash_file(full_path)

            if actual_hash is None:
                print(f"MISSING: {rel_path_str}")
                errors += 1
            elif actual_hash != expected_hash:
                print(f"TAMPERED: {rel_path_str}")
                errors += 1

        # (Optional) Check for unlisted files?
        # For v1, we only check that *known* files match.
        # Detecting injected unknown files is O(N) scan, maybe v2.

        if errors > 0:
            print(f"INTEGRITY FAILURE: {errors} violations detected.")
            if self.strict:
                print("SYSTEM HALT. Re-sign the codebase to proceed.")
                sys.exit(1)
        else:
            print("INTEGRITY CONFIRMED: Codebase is Sovereign.")
            self.verified = True

    def _verify_signature(self, manifest: dict) -> bool:
        """Verify the ML-DSA-65 signature of the manifest content."""
        if "signature" not in manifest or "files" not in manifest:
            return False

        signature_hex = manifest["signature"]

        # Canonicalize payload: standard json dump with sort_keys
        message = json.dumps(manifest["files"], sort_keys=True)

        if not PUB_KEY_PATH.exists():
            print(f" Public Key Missing: {PUB_KEY_PATH}")
            return False

        try:
            with open(PUB_KEY_PATH, "rb") as key_file:
                # Expecting B64 encoded HEX public key (Convention from an earlier revision)
                # or raw hex.
                content = key_file.read().strip()
                try:
                    # Try B64 decode first
                    public_key_hex = base64.b64decode(content).decode("utf-8")
                except Exception:
                    # Fallback to raw content if not b64
                    public_key_hex = content.decode("utf-8")

            mldsa = MLDSA()
            # MLDSA.verify(message: str, signature: str, public_key: str) -> bool
            is_valid = mldsa.verify(message, signature_hex, public_key_hex)

            if not is_valid:
                print("[Provenance] PQC Signature Verification FAILED.")

            return is_valid
        except Exception as e:
            print(f"Signature Verification Error: {e}")
            return False


# --- Genetic Integrity (Self-Replication) ---


class GeneticIntegrityGuard:
    """
    Advanced Integrity via Self-Replication Engine.
    Uses SovereignCodebase to verify that the running code matches the
    immutable blobs stored in the SovereignStore.
    """

    def __init__(
        self, store: SovereignStore, root_path: Optional[Union[str, Path]] = None
    ):
        self.store = store
        self.root = Path(root_path) if root_path else ROOT_DIR
        self.codebase = SovereignCodebase(self.store)

    def verify(self) -> str:
        """
        Ingests current codebase and returns the Genetic Hash (Manifest Hash).
        This hash serves as the 'DNA' of the kernel for swarm discovery.
        """
        print(f"[Genetic] Scanning codebase for DNA signature at {self.root}...")
        count = self.codebase.ingest(str(self.root))
        genetic_hash = self.codebase.generate_manifest()

        print(f"[Genetic] Ingested {count} files.")
        print(f"[Genetic] DNA Hash: {genetic_hash[:16]}...")

        # Verify integrity against what was just stored
        if not self.codebase.verify_integrity(str(self.root)):
            print("[Genetic] CRITICAL: Codebase integrity Check Failed!")
            sys.exit(1)

        return genetic_hash


# Easy entry point
def audit_guard() -> None:
    # Legacy Audit
    legacy = CodeIntegrityGuard(strict=False)  # Transitioning to Genetic
    legacy.enforce()

    # Genetic Audit
    store = SovereignStore()
    genetic = GeneticIntegrityGuard(store)
    genetic.verify()
    print("[Debug] audit_guard completed, returning to server.")
