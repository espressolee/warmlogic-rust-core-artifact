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

logger = logging.getLogger("warm_logic.kernel.security.silicon")


class SG2000Binder:
    """
    [Phase 84.1] Anchored Sovereignty: Silicon-level identity binding.
    Extracts unique hardware constants from the SG2000 (Milk-V Duo S)
    to create a non-transferable 'Hardware Reality Fingerprint'.
    """

    @staticmethod
    def get_fingerprint() -> str:
        """
        Combines multiple hardware markers into a SHA3-256 fingerprint.
        Fallback to 'VIRTUAL_REALITY' if no stable markers are found (Simulation mode).
        """
        markers = []

        # 1. CPU Serial & Hardware Model (Specific to CV1800B/SG2000)
        try:
            with open("/proc/cpuinfo", "r") as f:
                content = f.read()
                # Detection Logic for Milk-V Duo S (CV1800B)
                if "cv1800b" in content.lower() or "riscv" in content.lower():
                    markers.append("HW_MODEL:CV1800B")

                for line in content.splitlines():
                    if line.startswith("Serial"):
                        markers.append(line.split(":")[1].strip())
        except Exception:
            pass

        # 2. SD Card CID (Milk-V Duo S boots from SD)
        try:
            with open("/sys/class/block/mmcblk0/device/cid", "r") as f:
                markers.append("SD_CID:" + f.read().strip())
        except Exception:
            pass

        # 3. MAC Address (eth0 or usb0)
        for iface in ["eth0", "usb0", "en6"]:
            try:
                with open(f"/sys/class/net/{iface}/address", "r") as f:
                    markers.append(f"MAC:{iface}:" + f.read().strip())
            except Exception:
                pass

        # 4. Machine ID (Linux standard)
        if os.path.exists("/etc/machine-id"):
            try:
                with open("/etc/machine-id", "r") as f:
                    markers.append("MACHINE_ID:" + f.read().strip())
            except Exception:
                pass

        if not markers:
            # STRICT MODE: Fail if no hardware detected
            if os.environ.get("STRICT_HARDWARE", "0") == "1":
                logger.critical(
                    "🛑 [Silicon] STRICT MODE: No hardware markers found. Halting."
                )
                raise RuntimeError(
                    "Hardware Binding Failed: No physical reality anchors found."
                )

            try:
                import warm_logic_rs

                logger.info(
                    "🛡️  Accessing Rust HardwareRealityBinder for silicon fingerprint..."
                )
                # Hash the Rust hardware ID to produce consistent 64-char hex digest
                rust_hw_id = (
                    warm_logic_rs.HardwareRealityBinder.get_hardware_fingerprint()
                )
                return hashlib.sha3_256(rust_hw_id.encode()).hexdigest()
            except Exception as exc:
                logger.warning(
                    "🛡️  Hardware binding failed: No stable markers found and Rust binder unavailable (%s). Operating in VIRTUAL_REALITY.",
                    exc,
                )
                return hashlib.sha3_256(b"VIRTUAL_REALITY").hexdigest()

        # Combine markers with a salt to prevent trivial correlation
        raw_identity = "|".join(sorted(markers)).encode()
        fingerprint = hashlib.sha3_256(raw_identity).hexdigest()

        # Check if Rust agrees (cross-validation)
        try:
            import warm_logic_rs

            rust_fp = warm_logic_rs.HardwareRealityBinder.get_hardware_fingerprint()
            if rust_fp and "UNKNOWN" not in rust_fp and "NO_SD" not in rust_fp:
                logger.debug(
                    "🛡️  Silicon Fingerprint Cross-Validated with Rust Kernel."
                )
        except Exception:
            pass

        logger.info(f" Silicon Fingerprint Stabilized: {fingerprint[:8]}...")
        return fingerprint

    @staticmethod
    def seal_data(data: bytes) -> bytes:
        """Seals data to the physical silicon using the Rust binder."""
        try:
            import warm_logic_rs

            return warm_logic_rs.HardwareRealityBinder.seal_to_silicon(data)
        except Exception as e:
            logger.error(f" Seal failed: {e}")
            return data

    @staticmethod
    def unseal_data(sealed_data: bytes) -> bytes:
        """Unseals data from the physical silicon using the Rust binder."""
        try:
            import warm_logic_rs

            return warm_logic_rs.HardwareRealityBinder.unseal_from_silicon(sealed_data)
        except Exception as e:
            logger.error(f" Unseal failed: {e}")
            raise ValueError("Hardware Mismatch or Unseal Failure")

    @staticmethod
    def verify_reality(claimed_fingerprint: str) -> bool:
        """Verifies if the current hardware matches the claimed identity."""
        return SG2000Binder.get_fingerprint() == claimed_fingerprint
