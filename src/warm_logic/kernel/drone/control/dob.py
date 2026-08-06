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
Disturbance Observer (DOB) for Drone Control.
[Phase 126] Adaptation & Navigation
Estimates external forces (wind/gusts) by comparing commanded vs. measured acceleration.
"""

from typing import Tuple

from .filter import LowPassFilter


class DisturbanceObserver:
    """
    Estimates disturbance forces acting on the drone.
    Ref: "Disturbance Observer-Based Control" (Chen et al. 2016)

    Model: m * a_measured = F_thrust + F_disturbance
    Hence: F_disturbance = m * a_measured - F_thrust
    """

    def __init__(self, mass: float = 2.5, dt: float = 0.01, cutoff_hz: float = 0.5):
        self.mass = mass
        self.dt = dt

        # Low-pass filters for each axis to smooth out sensor noise and focus on low-freq disturbances (wind)
        self._filter_x = LowPassFilter(cutoff_freq_hz=cutoff_hz, dt=dt)
        self._filter_y = LowPassFilter(cutoff_freq_hz=cutoff_hz, dt=dt)
        self._filter_z = LowPassFilter(cutoff_freq_hz=cutoff_hz, dt=dt)

        self.reset()

    def update(
        self,
        measured_accel_body: Tuple[float, float, float],
        commanded_accel_body: Tuple[float, float, float],
    ) -> Tuple[float, float, float]:
        """
        Update the disturbance estimate.

        Args:
            measured_accel_body: Accel from IMU (bx, by, bz) in m/s^2
            commanded_accel_body: Accel commanded by the PID loops in m/s^2

        Returns:
            Estimated disturbance acceleration (dx, dy, dz) in m/s^2
        """
        # Disturbance = Measured - Commanded
        dist_x = measured_accel_body[0] - commanded_accel_body[0]
        dist_y = measured_accel_body[1] - commanded_accel_body[1]
        dist_z = measured_accel_body[2] - commanded_accel_body[2]

        # Filter to isolate persistent disturbances (wind) from high-frequency noise/vibration
        out_x = self._filter_x.update(dist_x)
        out_y = self._filter_y.update(dist_y)
        out_z = self._filter_z.update(dist_z)

        return (out_x, out_y, out_z)

    def reset(self) -> None:
        """Reset internal filters."""
        self._filter_x.reset()
        self._filter_y.reset()
        self._filter_z.reset()
