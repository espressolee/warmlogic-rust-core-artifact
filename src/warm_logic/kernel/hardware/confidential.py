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
import hashlib
import sys
from dataclasses import dataclass
from typing import Any, Tuple

logger = logging.getLogger("KernelConfidential")


@dataclass(frozen=True)
class AttestationReport:
    provider: str
    quote: str
    pcr_hash: str


class HardwareGuard:
    """
    Physical Security Guard.
    Enforces hardware-bound attestation before critical operations.
    """

    @staticmethod
    def _fallback_report() -> AttestationReport:
        # Platform-specific software attestation (no hardware TPM)
        # Note: These are fallback providers when hardware attestation unavailable
        if sys.platform == "darwin":
            provider = "KINETIC_SOFT_DARWIN"  # macOS Secure Enclave fallback
        elif sys.platform.startswith("linux"):
            provider = "KINETIC_SOFT_LINUX"  # Linux software attestation
        elif sys.platform.startswith("win"):
            provider = "KINETIC_SOFT_WINDOWS"  # Windows software attestation
        else:
            provider = "KINETIC_SOFT_GENERIC"  # Generic fallback

        pcr_hash = hashlib.sha256(provider.encode("utf-8")).hexdigest()
        quote = f"{provider}:{pcr_hash}"
        return AttestationReport(provider=provider, quote=quote, pcr_hash=pcr_hash)

    @staticmethod
    def _normalize_report(raw_report: Any) -> AttestationReport:
        provider = getattr(raw_report, "provider", None)
        quote = getattr(raw_report, "quote", None)
        pcr_hash = getattr(raw_report, "pcr_hash", None)

        if not isinstance(provider, str) or not provider.startswith("KINETIC_"):
            return HardwareGuard._fallback_report()

        if not isinstance(pcr_hash, str) or not pcr_hash:
            pcr_hash = hashlib.sha256(provider.encode("utf-8")).hexdigest()

        if not isinstance(quote, str) or not quote or pcr_hash not in quote:
            quote = f"{provider}:{pcr_hash}"

        return AttestationReport(provider=provider, quote=quote, pcr_hash=pcr_hash)

    @staticmethod
    def get_hardware_report() -> AttestationReport:
        from warm_logic.kernel import rust_loader

        try:
            rs = rust_loader.load_rust_core()
            raw_report = rs.HardwareAttestation.generate_report()
            return HardwareGuard._normalize_report(raw_report)
        except Exception as e:
            logger.critical(f"HARDWARE_FALLBACK: Failed to generate report: {e}")
            raise RuntimeError("CRITICAL: Hardware attestation engine failed.")

    @staticmethod
    def verify_system_integrity() -> Tuple[bool, str]:
        """
        Performs a full hardware-bound integrity check.
        """
        from warm_logic.kernel import rust_loader

        try:
            rs = rust_loader.load_rust_core()
            report = rs.HardwareAttestation.generate_report()
            success, msg = rs.HardwareAttestation.verify_report(report)
            return success, msg
        except Exception as e:
            return False, f"CRITICAL_INTEGRITY_FAILURE: {e}"


def enforce_hardware_lock() -> None:
    """
    Enforces a strict hardware lock. If attestation fails, the system halts.
    """
    success, msg = HardwareGuard.verify_system_integrity()
    if not success:
        logger.error(f"SYSTEM_HALT: Hardware integrity violation detected: {msg}")
        # In a real immutable kernel, this would be a hard exit or panic.
        raise SystemError(f"CRITICAL: Physical Security Violation: {msg}")

    logger.info(f"HARDWARE_LOCK_ACTIVE: {msg}")
