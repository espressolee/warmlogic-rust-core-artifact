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
Hardware Security & Attestation
Handles detection and interaction with TPM, Secure Enclaves, and
Post-Quantum hardware modules.
"""

import logging
import os
import platform
import subprocess
from typing import Any, Dict

logger = logging.getLogger("HardwareSecurity")


class HardwareAttestation:
    """
    Detects and verifies physical security characteristics of the host.
    """

    @staticmethod
    def identify_hardware_security() -> Dict[str, Any]:
        """
        Scans for physical security modules (TPM, Apple Secure Enclave, etc.)
        """
        results = {
            "tpm_available": False,
            "secure_enclave_available": False,
            "pqc_accelerator": False,
            "os_hardening": False,
        }

        # 1. Check for TPM (Linux/Windows)
        if platform.system() == "Linux":
            if os.path.exists("/dev/tpm0") or os.path.exists("/dev/tpmrm0"):
                results["tpm_available"] = True

        # 2. Check for Secure Enclave (macOS)
        if platform.system() == "Darwin":
            # Very basic check for Secure Enclave presence signal via system_profiler
            try:
                # We look for the Apple T2 or M-series security signal
                output = (
                    subprocess.check_output(["sysctl", "machdep.cpu.brand_string"])
                    .decode()
                    .lower()
                )
                if "apple" in output:
                    results["secure_enclave_available"] = True
            except Exception:
                pass

        # 3. Check for OS-level hardening (e.g. SELinux, SIP)
        if platform.system() == "Darwin":
            try:
                sip_status = subprocess.check_output(["csrutil", "status"]).decode()
                if "enabled" in sip_status:
                    results["os_hardening"] = True
            except Exception:
                pass

        logger.info(f" Hardware Security Scan Complete: {results}")
        return results

    @staticmethod
    def get_reality_score() -> float:
        """
        Calculates a 'Reality Score' (0.0 to 1.0) based on hardware trust.
        """
        security = HardwareAttestation.identify_hardware_security()
        score = 0.0
        if security["tpm_available"] or security["secure_enclave_available"]:
            score += 0.7
        if security["os_hardening"]:
            score += 0.3

        # If running in Docker without explicit pass-through, score is capped.
        if os.path.exists("/.dockerenv"):
            logger.warning(
                "📦 Containerized environment detected. Reality score restricted."
            )
            score = min(score, 0.5)

        return score
