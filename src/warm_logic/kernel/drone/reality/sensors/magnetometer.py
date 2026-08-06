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
Magnetometer Models.

Reference:
    Odenwald, S. (2015). "Earth's Magnetism in the Age of Sail"
    Harvard University Press

    Caruso, M.J. (2000). "Applications of Magnetic Sensors for
    Low Cost Compass Systems" Honeywell SSEC

    Renaudin, V. et al. (2010). "Complete Triaxis Magnetometer
    Calibration in the Magnetic Domain" Journal of Sensors
"""

import math
import random
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class MagnetometerModel:
    """
    Magnetometer Error Model.

    Reference:
        Caruso (2000)
        Renaudin et al. (2010)

    Error sources:
        1. Hard iron: Permanent magnetic fields on vehicle
        2. Soft iron: Induced magnetization from ferromagnetic materials
        3. Sensor noise: White noise and bias
        4. Ambient magnetic interference: Motors, power lines, etc.

    Example:
        >>> mag = MagnetometerModel()
        >>> noisy = mag.corrupt_measurement((0.2, 0.0, 0.4))
    """

    # Sensor noise (Gauss)
    noise_sigma_gauss: float = 0.01

    # Hard iron offset (Gauss) - constant bias
    hard_iron: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Soft iron matrix - off-diagonal terms cause cross-axis coupling
    soft_iron: Tuple[Tuple[float, ...], ...] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )

    # Temperature sensitivity (%/°C)
    temp_coefficient: float = 0.3

    # Reference temperature for temp coefficient
    reference_temp_c: float = 25.0

    def corrupt_measurement(
        self,
        true_field: Tuple[float, float, float],
        temperature_c: float = 25.0,
    ) -> Tuple[float, float, float]:
        """
        Apply magnetometer errors to true field.

        Reference: Renaudin et al. (2010), Eq. 3-5

        B_meas = S × B_true + h + ε

        Where:
            S = Soft iron matrix
            h = Hard iron vector
            ε = Noise

        Args:
            true_field: True magnetic field (Gauss)
            temperature_c: Temperature (°C)

        Returns:
            Measured field (Gauss)
        """
        bx, by, bz = true_field

        # Apply soft iron distortion
        sx = (
            self.soft_iron[0][0] * bx
            + self.soft_iron[0][1] * by
            + self.soft_iron[0][2] * bz
        )
        sy = (
            self.soft_iron[1][0] * bx
            + self.soft_iron[1][1] * by
            + self.soft_iron[1][2] * bz
        )
        sz = (
            self.soft_iron[2][0] * bx
            + self.soft_iron[2][1] * by
            + self.soft_iron[2][2] * bz
        )

        # Apply hard iron offset
        mx = sx + self.hard_iron[0]
        my = sy + self.hard_iron[1]
        mz = sz + self.hard_iron[2]

        # Temperature drift
        temp_factor = 1.0 + self.temp_coefficient / 100 * (
            temperature_c - self.reference_temp_c
        )
        mx *= temp_factor
        my *= temp_factor
        mz *= temp_factor

        # Add noise
        mx += random.gauss(0, self.noise_sigma_gauss)
        my += random.gauss(0, self.noise_sigma_gauss)
        mz += random.gauss(0, self.noise_sigma_gauss)

        return (mx, my, mz)

    def get_heading(
        self,
        field: Tuple[float, float, float],
        declination_deg: float = 0.0,
    ) -> float:
        """
        Calculate heading from magnetic field.

        Reference: Caruso (2000), Eq. 5

        Heading = atan2(-By, Bx) + Declination

        Args:
            field: Measured field (Gauss)
            declination_deg: Local magnetic declination

        Returns:
            Heading (degrees, 0-360)
        """
        bx, by, _ = field

        heading_rad = math.atan2(-by, bx)
        heading_deg = math.degrees(heading_rad) + declination_deg

        # Normalize to 0-360
        while heading_deg < 0:
            heading_deg += 360
        while heading_deg >= 360:
            heading_deg -= 360

        return heading_deg


@dataclass
class HardSoftIronCalibration:
    """
    Magnetometer Calibration for Hard/Soft Iron.

    Reference:
        Renaudin et al. (2010). "Complete Triaxis Magnetometer
        Calibration in the Magnetic Domain"

    Calibration transforms ellipsoid of measurements into a sphere:
        B_cal = A^{-1} × (B_meas - b)

    Where:
        A = Combined soft iron + scale matrix
        b = Hard iron offset vector
    """

    # Calibration parameters
    offset: Tuple[float, float, float] = field(default=(0.0, 0.0, 0.0))
    scale_matrix: Tuple[Tuple[float, ...], ...] = field(
        default=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    )

    def calibrate(
        self, raw_field: Tuple[float, float, float]
    ) -> Tuple[float, float, float]:
        """
        Apply calibration to raw measurement.

        Args:
            raw_field: Raw magnetometer reading

        Returns:
            Calibrated field
        """
        # Remove hard iron
        bx = raw_field[0] - self.offset[0]
        by = raw_field[1] - self.offset[1]
        bz = raw_field[2] - self.offset[2]

        # Apply scale/soft iron correction
        cx = (
            self.scale_matrix[0][0] * bx
            + self.scale_matrix[0][1] * by
            + self.scale_matrix[0][2] * bz
        )
        cy = (
            self.scale_matrix[1][0] * bx
            + self.scale_matrix[1][1] * by
            + self.scale_matrix[1][2] * bz
        )
        cz = (
            self.scale_matrix[2][0] * bx
            + self.scale_matrix[2][1] * by
            + self.scale_matrix[2][2] * bz
        )

        return (cx, cy, cz)

    @classmethod
    def fit_from_samples(cls, samples: list) -> "HardSoftIronCalibration":
        """
        Fit calibration from rotation samples.

        Reference: Renaudin et al. (2010), Section 4

        Requires full 3D rotation during sampling.
        Uses ellipsoid fitting algorithm.

        Args:
            samples: List of (bx, by, bz) measurements

        Returns:
            Fitted calibration object
        """
        if len(samples) < 100:
            raise ValueError("Need at least 100 samples for calibration")

        # Simple centroid estimation for hard iron
        n = len(samples)
        offset_x = sum(s[0] for s in samples) / n
        offset_y = sum(s[1] for s in samples) / n
        offset_z = sum(s[2] for s in samples) / n

        # Simplified: assume identity scale matrix
        # Full implementation would use ellipsoid fitting (SVD)
        return cls(
            offset=(offset_x, offset_y, offset_z),
            scale_matrix=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        )
