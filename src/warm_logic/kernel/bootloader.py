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
"""[P0xx] Bootloader - Hardware validation and Rust core initialization."""

from typing import Any, Tuple

from warm_logic.kernel.hardware.confidential import HardwareGuard, enforce_hardware_lock
from warm_logic.kernel.rust_loader import HAS_RUST_CORE, load_rust_core


class Bootloader:
    def __init__(self) -> None:
        self.state = "OFFLINE"
        self._core = None

        # hardware attestation enforcement
        # We explicitly reject simulation mode to ensure sovereign integrity.
        import os

        if os.environ.get("WARM_LOGIC_SIMULATION") == "1":
            raise SystemError(
                "CRITICAL: Simulation Mode Detected. hardware attestation enforcement Active."
            )

    def run_init(self) -> bool:
        """
        Initializes the Kinetic Core and performs hardware binding.
        """
        if not HAS_RUST_CORE:
            raise RuntimeError("CRITICAL: Rust Core missing. Cannot initialize.")

        rs = load_rust_core()
        self._core = rs.KineticCore()
        self.state = "INITIALIZED"
        return True

    def verify_secure_boot(self) -> Tuple[bool, str]:
        """
        Verifies the 'Sealed' state via real hardware attestation.
        """
        success, msg = HardwareGuard.verify_system_integrity()
        if success:
            self.state = "SECURE_BOOT_VERIFIED"
        else:
            self.state = "ATTESTATION_FAILED"
        return success, msg

    def jump_to_kernel(self) -> Any:
        if self.state != "SECURE_BOOT_VERIFIED":
            raise RuntimeError(f"CRITICAL: Kernel jump blocked. State: {self.state}")
        self.state = "RUNNING"
        return self._core


def boot_system() -> Any:
    loader = Bootloader()
    loader.run_init()

    # Enforce strict hardware lock
    enforce_hardware_lock()

    sealed, proof = loader.verify_secure_boot()
    if not sealed:
        raise RuntimeError(f"SYSTEM_HALT: Attestation Failed: {proof}")

    return loader.jump_to_kernel()
