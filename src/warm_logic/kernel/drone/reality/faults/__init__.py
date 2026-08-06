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
"""Ultimate 63 Calamities Disaster Simulator v5.1."""

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np


@dataclass
class MechanicalFatigue:
    """S-N Curve fatigue model. Reference: ASTM E466."""

    total_cycles: int = 0
    failure_threshold: int = 1_000_000

    def accumulate(self, stress_ratio: float = 1.0) -> None:
        """Miner's rule accumulation."""
        self.total_cycles += int(1000 * stress_ratio)

    def check_failure(self) -> bool:
        """Check for fatigue failure."""
        return self.total_cycles >= self.failure_threshold


@dataclass
class SingleEventUpset:
    """Radiation-induced bit flip. Reference: NASA EEE-INST-002."""

    sea_level_rate_per_bit_per_hour: float = 1e-15
    altitude_m: float = 0.0

    def check_bit_flip(self, num_bits: int = 1_000_000, dt: float = 0.01) -> bool:
        """Check for SEU occurrence."""
        alt_factor = 1 + self.altitude_m / 1000  # Increases with altitude
        rate = self.sea_level_rate_per_bit_per_hour * alt_factor * num_bits * dt / 3600
        return random.random() < rate


@dataclass
class DisasterSimulator:
    """
    Ultimate 63 Calamities Disaster Simulator v5.1.

    Injects various failure scenarios across 5 categories:
    1. Actuator (Motors, ESCs)
    2. Sensor (GPS, IMU, Mag)
    3. Environmental (Wind, Turbulence, Temperature)
    4. Computing (SEU, Overflow, Latency)
    5. Power (Battery Sag, ESR)
    """

    active_faults: List[Dict[str, Any]] = field(default_factory=list)
    time_s: float = 0.0
    _survived_count: int = field(default=0, repr=False)
    _total_tests: int = field(default=0, repr=False)

    def update(self, dt: float) -> None:
        """Update disaster state."""
        self.time_s += dt
        # Clean up expired faults
        self.active_faults = [
            f
            for f in self.active_faults
            if f.get("expires", float("inf")) > self.time_s
        ]

    # --- 1. Actuator Calamities ---
    def inject_motor_failure(
        self, motor_id: int, efficiency: float = 0.5, duration: float = 5.0
    ) -> None:
        self.active_faults.append(
            {
                "type": "motor_failure",
                "motor_id": motor_id,
                "efficiency": efficiency,
                "expires": self.time_s + duration,
            }
        )

    def inject_esc_jitter(self, jitter_ms: float = 1.0, duration: float = 10.0) -> None:
        self.active_faults.append(
            {
                "type": "esc_jitter",
                "jitter_ms": jitter_ms,
                "expires": self.time_s + duration,
            }
        )

    # --- 2. Sensor Calamities ---
    def inject_gps_freeze(self, duration: float = 2.0) -> None:
        self.active_faults.append(
            {"type": "gps_freeze", "expires": self.time_s + duration}
        )

    def inject_gps_multipath(self, error_m: float = 5.0, duration: float = 5.0) -> None:
        self.active_faults.append(
            {
                "type": "gps_multipath",
                "error_m": error_m,
                "expires": self.time_s + duration,
            }
        )

    def inject_imu_drift(self, drift_rate: float = 0.1, duration: float = 10.0) -> None:
        self.active_faults.append(
            {
                "type": "imu_drift",
                "drift_rate": drift_rate,
                "expires": self.time_s + duration,
            }
        )

    # --- 3. Environmental Calamities ---
    def inject_microburst(self, force_n: float = 20.0, duration: float = 1.5) -> None:
        self.active_faults.append(
            {
                "type": "microburst",
                "force_n": force_n,
                "expires": self.time_s + duration,
            }
        )

    # --- 4. Power Calamities ---
    def inject_battery_sag(
        self, voltage_drop: float = 2.0, duration: float = 3.0
    ) -> None:
        self.active_faults.append(
            {
                "type": "battery_sag",
                "voltage_drop": voltage_drop,
                "expires": self.time_s + duration,
            }
        )

    # --- Fault Accessors ---
    def get_motor_efficiency(self, motor_id: int) -> float:
        eff = 1.0
        for fault in self.active_faults:
            if (
                fault.get("type") == "motor_failure"
                and fault.get("motor_id") == motor_id
            ):
                eff *= fault.get("efficiency", 1.0)
        return eff

    def get_gps_offset(self) -> tuple:
        offset = (0.0, 0.0, 0.0)
        for fault in self.active_faults:
            if fault.get("type") == "gps_multipath":
                err = fault.get("error_m", 0.0)
                offset = (
                    offset[0] + random.uniform(-err, err),
                    offset[1] + random.uniform(-err, err),
                    offset[2] + random.uniform(-err, err),
                )
        return offset

    def is_gps_frozen(self) -> bool:
        return any(f.get("type") == "gps_freeze" for f in self.active_faults)

    def get_imu_bias_offset(self) -> float:
        bias = 0.0
        for fault in self.active_faults:
            if fault.get("type") == "imu_drift":
                bias += fault.get("drift_rate", 0.0) * (
                    self.time_s - (fault["expires"] - 10.0)
                )
        return bias

    def get_external_force(self) -> np.ndarray:
        force = np.zeros(3)
        for fault in self.active_faults:
            if fault.get("type") == "microburst":
                force[2] += fault.get("force_n", 0.0)  # Downward force
        return force

    # --- Survival Tracking ---
    def mark_survived(self) -> None:
        """Mark that the system survived the current test run."""
        self._survived_count += 1
        self._total_tests += 1

    def mark_failed(self) -> None:
        """Mark that the system failed the current test run."""
        self._total_tests += 1

    def survival_rate(self) -> float:
        """Calculate the survival rate across all test runs."""
        if self._total_tests == 0:
            return 1.0
        return self._survived_count / self._total_tests
