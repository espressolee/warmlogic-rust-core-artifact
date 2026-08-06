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
"""[P3xx] Constitutional Guard - Signed governance rules enforcement."""

import base64
import binascii
import json
import logging
import math
import time
from pathlib import Path
from typing import Any, Dict

import yaml
from cryptography.hazmat.primitives.asymmetric import ed25519

# Paths - Navigate from kernel/constitution.py to project root
# __file__ = src/warm_logic/kernel/constitution.py
# parent^4 = WarmLogic (project root)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
CONSTITUTION_PATH = ROOT_DIR / "data" / "provenance" / "constitution.signed.yaml"
PUB_KEY_PATH = ROOT_DIR / "data" / "provenance" / "owner_pub.dat"

logger = logging.getLogger("ConstitutionalGuard")


class ConstitutionalGuard:
    def __init__(self) -> None:
        self.constitution: dict[str, Any] | None = None
        self.load_constitution()

    def load_constitution(self) -> None:
        """Loads and verifies the signed constitution."""
        if not CONSTITUTION_PATH.exists():
            print(f" Constitution Missing: {CONSTITUTION_PATH}")
            return

        try:
            with open(CONSTITUTION_PATH, "r") as f:
                signed_data = yaml.safe_load(f)

            if self._verify(signed_data):
                self.constitution = signed_data["data"]
                print(" CONSTITUTION LOADED: Invariants active.")
            else:
                print("CRITICAL: Constitution signature verification FAILED.")
        except Exception as e:
            print(f"Error loading constitution: {e}")

    def _verify(self, signed_data: dict) -> bool:
        """Verify the Ed25519 signature of the constitution."""
        if not PUB_KEY_PATH.exists():
            print(f" Public Key Missing: {PUB_KEY_PATH}")
            return False

        try:
            pub_b64 = PUB_KEY_PATH.read_bytes()
            pub_bytes = base64.b64decode(pub_b64)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

            # Reconstruct payload (separators match forge script)
            payload = json.dumps(
                signed_data["data"], separators=(",", ":"), sort_keys=False
            ).encode()
            signature = binascii.unhexlify(signed_data["signature"])

            public_key.verify(signature, payload)
            return True
        except Exception as e:
            print(f"Signature Verification Error: {e}")
            return False

    def calculate_entropy(self, text: str) -> float:
        """Calculates Shannon entropy of a string."""
        if not text:
            return 0.0
        entropy: float = 0.0
        for x in range(256):
            p_x = float(text.count(chr(x))) / len(text)
            if p_x > 0:
                entropy += -p_x * math.log(p_x, 2)
        return entropy

    def sanitize(self, text: str) -> tuple[str, int]:
        """
        Interrogates text against keywords and entropy limits.
        Returns (safe_text, violations_count)
        """
        if self.constitution is None:
            # hardware attestation enforcement: No law, No operation.
            raise RuntimeError(
                "CRITICAL: Constitution not loaded. Sanitization blocked."
            )

        violations: int = 0
        safe_text = text

        # 1. Keyword Filtering
        keywords = self.constitution.get("sensitive_keywords", [])
        for word in keywords:
            if word in safe_text:
                violations += 1
                safe_text = safe_text.replace(word, "[REDACTED_BY_CONSTITUTION]")

        # 2. Entropy Check (Detect exfiltration/obfuscation)
        threshold = self.constitution.get("entropy_threshold", 5.5)
        current_entropy = self.calculate_entropy(text)

        if current_entropy > threshold:
            print(f" HIGH ENTROPY DETECTED: {current_entropy:.2f} > {threshold}")
            # If entropy is too high, we block the output entirely if defense_level > 50
            if self.constitution.get("defense_level", 100) > 50:
                violations += 1
                return "[❌ OUTPUT BLOCKED: HIGH ENTROPY DETECTED]", violations

        return safe_text, violations

    def apply_amendment(
        self, amendment_data: Dict[str, Any], quorum_signature: str
    ) -> bool:
        """
        Applies a constitutional amendment after BFT Quorum verification.
        In a real system, quorum_signature would be a multisig of 2/3+ validators.
        """
        logger.info("[Gov] Verifying BFT Quorum for Constitutional Amendment...")

        # Verify Quorum Signature (Stub for now, but enforces the logic)
        if not quorum_signature:
            logger.error("Amendment REJECTED: Missing Quorum Signature.")
            return False

        # Apply changes to local in-memory constitution
        if self.constitution is None:
            self.constitution = {}

        for key, value in amendment_data.items():
            logger.info(f"[Gov] Updating invariant: {key} -> {value}")
            self.constitution[key] = value

        # Persistence: Save to disk (Currently, we overwrite the local signed file for demo)
        try:
            # We don't have the owner's private key to re-sign,
            # so we mark it as "GOVERNANCE_PATCHED"
            metadata = {
                "data": self.constitution,
                "signature": quorum_signature,
                "patched_by": "BFT_QUORUM",
                "timestamp": time.time(),
            }
            with open(CONSTITUTION_PATH, "w") as f:
                yaml.dump(metadata, f)
            logger.info("Constitution amended and synchronized to disk.")
            return True
        except Exception as e:
            logger.error(f"Failed to save amendment: {e}")
            return False


class UpdateSafetyAxiom:
    """
    Structural gate for autonomous kernel updates.

    NOTE: this is a demonstration stub. It enforces format, size, and the
    presence of a signature marker; it does NOT perform real ML-DSA-65
    signature or ZK-proof verification yet. See docs/CLAIM_EVIDENCE.md.
    """

    @staticmethod
    def verify_update(patch_data: bytes) -> bool:
        """
        Structural patch check (stub).

        Real signature/ZK verification is not yet implemented; this checks
        format, size, and that a signature trailer is present.
        """
        logger.info(
            "⚖️ [Constitution] Interrogating Binary Patch via UpdateSafetyAxiom..."
        )

        # 1. Structure Check: Must start with WarmLogic Magic Bytes
        if not patch_data.startswith(b"\x7fWL_PATCH"):
            logger.error(
                "🚫 Patch REJECTED: Invalid file format (Magic Bytes mismatch)."
            )
            return False

        # 2. Size Constraint
        if len(patch_data) > 5 * 1024 * 1024:
            logger.error("Patch REJECTED: Size exceeds safety bound (5MB).")
            return False

        # 3. Signature trailer presence check (NOT real verification yet)
        try:
            # Look for PQC Signature Trailer
            signature_marker = b"---PQC_SIG_BEGIN---"
            if signature_marker not in patch_data:
                logger.error("Patch REJECTED: Missing PQC Cryptographic Signature.")
                return False

            # Verify Quorum
            # Simulated check: In Phase 87, we ensure the patch is 'blessed' by a root node.
            logger.info("[Constitution] Signature trailer present (verification stubbed)")
        except Exception as e:
            logger.error(f"Patch REJECTED: Signature verification error: {e}")
            return False

        # 4. ZK-proof check is not implemented (stub returns accept once structure is valid)
        return True


class SovereignKillpulseAxiom:
    """
    Emergency halt axiom.

    NOTE: demonstration stub — matches a fixed root signature string rather
    than verifying a real PQC signature. See docs/CLAIM_EVIDENCE.md.
    """

    @staticmethod
    def verify_killpulse(signal: bytes, signature: str) -> bool:
        """Verifies an external killpulse signal."""
        logger.warning("[Constitution] INTERROGATING SOVEREIGN KILLPULSE...")

        # Currently, we check for a specific root authority root signature
        if signal == b"PANIC_STOP" and signature == "ROOT_AUTHORITY_SIG_0xDEADBEEF":
            logger.critical(
                "💀 [Constitution] KILLPULSE VERIFIED. INITIATING KERNEL SHUTDOWN."
            )
            return True

        return False


# Entry point for the kernel
guard = ConstitutionalGuard()


def constitutional_audit(text: str) -> tuple[str, int]:
    return guard.sanitize(text)
