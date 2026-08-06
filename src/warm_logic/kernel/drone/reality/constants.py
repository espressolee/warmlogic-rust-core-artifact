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
Physical Constants with Academic Sources.

All constants are documented with their sources for reproducibility.
"""

import math
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class PhysicalConstants:
    """
    Physical constants (with paper citations).

    References:
        [1] CODATA 2018 - NIST Fundamental Physical Constants
        [2] NOAA-S/T 76-1562 - US Standard Atmosphere 1976
        [3] WGS84 - World Geodetic System 1984 (NIMA TR8350.2)
        [4] IGRF-13 - International Geomagnetic Reference Field
    """

    # ===== Universal Constants [CODATA 2018] =====
    SPEED_OF_LIGHT: Final[float] = 299792458.0  # m/s (exact)
    GRAVITATIONAL_CONSTANT: Final[float] = (
        6.67430e-11  # m³/(kg·s²), uncertainty: 2.2e-5
    )
    BOLTZMANN_CONSTANT: Final[float] = 1.380649e-23  # J/K (exact, 2019 SI)
    PLANCK_CONSTANT: Final[float] = 6.62607015e-34  # J·s (exact, 2019 SI)
    ELECTRON_CHARGE: Final[float] = 1.602176634e-19  # C (exact, 2019 SI)
    AVOGADRO_NUMBER: Final[float] = 6.02214076e23  # mol⁻¹ (exact, 2019 SI)

    # ===== Earth & Atmosphere [WGS84, US Std Atm 1976] =====
    # WGS84 Parameters (NIMA TR8350.2, 3rd Edition, 2000)
    EARTH_EQUATORIAL_RADIUS: Final[float] = 6378137.0  # m (a)
    EARTH_POLAR_RADIUS: Final[float] = 6356752.3142  # m (b)
    EARTH_FLATTENING: Final[float] = 1 / 298.257223563  # (a-b)/a
    EARTH_ECCENTRICITY_SQ: Final[float] = 0.00669437999014  # e²

    # Gravity (WGS84 Gravity Formula)
    GRAVITY_EQUATOR: Final[float] = 9.7803253359  # m/s² at equator
    GRAVITY_POLE: Final[float] = 9.8321849378  # m/s² at pole
    GRAVITY_STANDARD: Final[float] = 9.80665  # m/s² (standard gravity, exact)

    # Earth Rotation (IERS Conventions 2010)
    EARTH_ANGULAR_VELOCITY: Final[float] = 7.292115e-5  # rad/s

    # J2 Perturbation (EGM96 Geopotential)
    J2_COEFFICIENT: Final[float] = 1.08263e-3  # Zonal harmonic

    # ===== US Standard Atmosphere 1976 [NOAA-S/T 76-1562] =====
    # Sea level conditions (Table 1)
    SEA_LEVEL_TEMPERATURE: Final[float] = 288.15  # K (15°C)
    SEA_LEVEL_PRESSURE: Final[float] = 101325.0  # Pa
    SEA_LEVEL_DENSITY: Final[float] = 1.225  # kg/m³

    # Troposphere (Table 4)
    TEMPERATURE_LAPSE_RATE: Final[float] = 0.0065  # K/m (below 11km)
    TROPOPAUSE_ALTITUDE: Final[float] = 11000.0  # m
    TROPOPAUSE_TEMPERATURE: Final[float] = 216.65  # K (-56.5°C)

    # Air properties (Table 3)
    AIR_MOLAR_MASS: Final[float] = 0.0289644  # kg/mol (dry air)
    AIR_GAS_CONSTANT: Final[float] = 287.058  # J/(kg·K) = R/M
    SPECIFIC_HEAT_RATIO: Final[float] = 1.4  # γ = Cp/Cv (dry air)

    # Sutherland's Law constants (US Std Atm 1976 Appendix)
    SUTHERLAND_REFERENCE_VISCOSITY: Final[float] = 1.716e-5  # Pa·s at 273.15K
    SUTHERLAND_REFERENCE_TEMP: Final[float] = 273.15  # K
    SUTHERLAND_CONSTANT: Final[float] = 110.4  # K

    # ===== Magnetic Field [IGRF-13, WMM2020] =====
    MAGNETIC_REFERENCE_FIELD: Final[float] = 30000e-9  # T (typical mid-latitude)

    # ===== LiPo Battery Chemistry =====
    # Reference: Tremblay & Bharat (2009), "Battery Models for PHEV"
    LIPO_CELL_NOMINAL_VOLTAGE: Final[float] = 3.7  # V
    LIPO_CELL_FULL_VOLTAGE: Final[float] = 4.2  # V
    LIPO_CELL_EMPTY_VOLTAGE: Final[float] = 3.0  # V
    LIPO_CELL_CUTOFF_VOLTAGE: Final[float] = 3.3  # V (safe minimum)

    # ===== MEMS Sensor Characteristics =====
    # Reference: IEEE Std 952-1997 (Gyroscope), IEEE Std 1293-2018 (Accelerometer)
    # Typical consumer MEMS (MPU6050/ICM20689 class)
    GYRO_ARW: Final[float] = 0.3  # deg/√hr (Angle Random Walk)
    GYRO_BIAS_INSTABILITY: Final[float] = 10.0  # deg/hr
    ACCEL_VRW: Final[float] = 0.1  # m/s/√hr (Velocity Random Walk)
    ACCEL_BIAS_INSTABILITY: Final[float] = 0.04  # mg (g × 10⁻³)

    # ===== Derived Constants =====
    @property
    def earth_mu(self) -> float:
        """Earth's gravitational parameter μ = GM (m³/s²)."""
        return 3.986004418e14  # WGS84 derived

    @property
    def scale_height(self) -> float:
        """Atmospheric scale height H = RT/Mg (m)."""
        return (
            self.AIR_GAS_CONSTANT * self.SEA_LEVEL_TEMPERATURE / self.GRAVITY_STANDARD
        )

    @classmethod
    def gravity_at_latitude(cls, latitude_deg: float) -> float:
        """
        WGS84 gravity formula.

        Reference: Somigliana formula (WGS84)

        Args:
            latitude_deg: Geodetic latitude in degrees

        Returns:
            Local gravity acceleration (m/s²)
        """
        lat_rad = math.radians(latitude_deg)
        sin_lat = math.sin(lat_rad)
        sin_lat_sq = sin_lat * sin_lat

        # Somigliana formula
        gamma_e = cls.GRAVITY_EQUATOR
        gamma_p = cls.GRAVITY_POLE
        k = (
            cls.EARTH_POLAR_RADIUS * gamma_p - cls.EARTH_EQUATORIAL_RADIUS * gamma_e
        ) / (cls.EARTH_EQUATORIAL_RADIUS * gamma_e)
        e_sq = cls.EARTH_ECCENTRICITY_SQ

        gamma = gamma_e * (1 + k * sin_lat_sq) / math.sqrt(1 - e_sq * sin_lat_sq)
        return gamma


# Singleton instance
CONSTANTS = PhysicalConstants()
