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
GPS Error Models.

Reference:
    Kaplan, E.D. & Hegarty, C.J. (2017). "Understanding GPS/GNSS:
    Principles and Applications" 3rd Edition, Artech House

    Misra, P. & Enge, P. (2006). "Global Positioning System:
    Signals, Measurements, and Performance" 2nd Edition

Error Sources (Kaplan Ch. 7):
    1. Satellite ephemeris and clock errors
    2. Ionospheric delay
    3. Tropospheric delay
    4. Multipath
    5. Receiver noise
    6. Geometric dilution (GDOP)
"""

import math
import random
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class GPSErrorBudget:
    """
    GPS Error Budget (1-sigma values).

    Reference: Kaplan (2017), Table 7.1

    Typical standalone GPS accuracy budget (1σ):
        Ephemeris: 2.0 m
        Satellite clock: 2.0 m
        Ionosphere: 4.0 m (single freq, no model)
        Troposphere: 0.5 m
        Multipath: 1.0 m
        Receiver noise: 0.3 m

        UERE = √(sum of squares) ≈ 5 m (typical)
        3D Position = UERE × PDOP ≈ 10 m (horizontal)
    """

    ephemeris_m: float = 2.0
    satellite_clock_m: float = 2.0
    ionosphere_m: float = 4.0
    troposphere_m: float = 0.5
    multipath_m: float = 1.0
    receiver_noise_m: float = 0.3

    @property
    def uere(self) -> float:
        """User Equivalent Range Error (m)."""
        return math.sqrt(
            self.ephemeris_m**2
            + self.satellite_clock_m**2
            + self.ionosphere_m**2
            + self.troposphere_m**2
            + self.multipath_m**2
            + self.receiver_noise_m**2
        )


@dataclass
class GPSErrorModel:
    """
    Complete GPS Error Model.

    Reference:
        Kaplan (2017), Chapters 6-7
        Misra & Enge (2006), Chapter 5

    Models:
        - Static position error (UERE × DOP)
        - Dynamic tracking loop errors
        - Ionospheric/tropospheric delay
        - Satellite geometry (DOP)

    Example:
        >>> gps = GPSErrorModel()
        >>> noisy_pos = gps.corrupt_position(lat=37.5, lon=126.9, alt=100)
    """

    error_budget: GPSErrorBudget = field(default_factory=GPSErrorBudget)

    # Dilution of Precision (typical urban)
    hdop: float = 1.5
    vdop: float = 2.5
    pdop: float = 2.9

    # Visible satellites
    num_satellites: int = 8

    # Fix quality
    fix_type: str = "3D"  # "None", "2D", "3D", "DGPS", "RTK_Float", "RTK_Fixed"

    # Internal states
    _position_bias: Tuple[float, float, float] = field(
        default=(0.0, 0.0, 0.0), repr=False
    )

    def get_horizontal_accuracy(self) -> float:
        """
        Horizontal position accuracy (1σ, meters).

        Reference: Kaplan (2017), Eq. 7.1

        σ_H = UERE × HDOP
        """
        return self.error_budget.uere * self.hdop

    def get_vertical_accuracy(self) -> float:
        """
        Vertical position accuracy (1σ, meters).

        σ_V = UERE × VDOP
        """
        return self.error_budget.uere * self.vdop

    def corrupt_position(
        self,
        lat_deg: float,
        lon_deg: float,
        alt_m: float,
    ) -> Tuple[float, float, float]:
        """
        Add GPS errors to true position.

        Reference: Kaplan (2017), Section 7.2

        Args:
            lat_deg: True latitude (deg)
            lon_deg: True longitude (deg)
            alt_m: True altitude (m)

        Returns:
            (noisy_lat, noisy_lon, noisy_alt)
        """
        if self.fix_type == "None":
            return (float("nan"), float("nan"), float("nan"))

        # Horizontal error (north, east)
        h_error = self.get_horizontal_accuracy()
        north_error = random.gauss(0, h_error)
        east_error = random.gauss(0, h_error)

        # Convert to lat/lon (approximate)
        # 1 deg lat ≈ 111 km
        # 1 deg lon ≈ 111 km × cos(lat)
        lat_error = north_error / 111000
        lon_error = east_error / (111000 * math.cos(math.radians(lat_deg)))

        # Vertical error
        v_error = self.get_vertical_accuracy()
        alt_error = random.gauss(0, v_error)

        return (
            lat_deg + lat_error,
            lon_deg + lon_error,
            alt_m + alt_error,
        )

    def corrupt_velocity(
        self, true_vel: Tuple[float, float, float], dt: float
    ) -> Tuple[float, float, float]:
        """
        Add GPS velocity errors.

        Reference: Misra & Enge (2006), Section 5.6

        Doppler-derived velocity accuracy is typically
        0.1-0.3 m/s for consumer GPS.

        Args:
            true_vel: True NED velocity (m/s)
            dt: Time step (s)

        Returns:
            Noisy velocity (m/s)
        """
        vel_sigma = 0.1  # m/s (typical)

        return (
            true_vel[0] + random.gauss(0, vel_sigma),
            true_vel[1] + random.gauss(0, vel_sigma),
            true_vel[2] + random.gauss(0, vel_sigma * 1.5),  # Vertical worse
        )


@dataclass
class MultipathModel:
    """
    GPS Multipath Error Model.

    Reference:
        Kaplan (2017), Section 7.3.4
        Braasch, M.S. (1996). "Multipath Effects" in
        Global Positioning System: Theory and Applications, AIAA

    Multipath occurs when GPS signals reflect off nearby surfaces
    (buildings, ground, water) before reaching the receiver.

    Effects:
        - Range error: up to 50 m (code) or 0.05λ ≈ 1 cm (carrier)
        - Position jump when multipath appears/disappears
        - Worse in urban canyons
    """

    # Environment type
    environment: str = "open"  # "open", "suburban", "urban", "indoor"

    # Reflector parameters
    num_reflectors: int = 0
    max_path_delay_m: float = 50.0

    def get_multipath_error(self, satellite_elevation_deg: float) -> float:
        """
        Multipath range error based on satellite elevation.

        Reference: Kaplan (2017), Figure 7.10

        Low elevation satellites have more multipath because:
        1. Longer path through reflective environment
        2. More grazing angle reflections

        Args:
            satellite_elevation_deg: Satellite elevation (deg)

        Returns:
            Range error contribution (m)
        """
        if satellite_elevation_deg < 5:
            return 0.0  # Usually masked

        env_factors = {
            "open": 0.5,
            "suburban": 2.0,
            "urban": 10.0,
            "indoor": 50.0,
        }
        base = env_factors.get(self.environment, 2.0)

        # Error inversely proportional to elevation
        # Higher elevation = less multipath
        elevation_factor = 1.0 / (1.0 + 0.1 * satellite_elevation_deg)

        return base * elevation_factor * random.uniform(0.5, 1.5)

    def simulate_urban_canyon(
        self, true_lat: float, true_lon: float, canyon_width_m: float = 20
    ) -> Tuple[float, float]:
        """
        Simulate urban canyon multipath effect.

        Reference: Ochieng et al. (2003). "GPS Integrity and Potential
        Impact on Aviation Safety" Journal of Navigation

        Urban canyons cause:
        - Reduced satellite visibility
        - Strong multipath from building walls
        - Potential NLOS (non-line-of-sight) signals

        Args:
            true_lat, true_lon: True position
            canyon_width_m: Street width

        Returns:
            Error-affected (lat, lon)
        """
        # Narrow canyons have worse multipath
        error_scale = 30.0 / max(10, canyon_width_m)

        # Random "teleport" due to NLOS
        lat_jump = random.gauss(0, error_scale) / 111000
        lon_jump = random.gauss(0, error_scale) / (
            111000 * math.cos(math.radians(true_lat))
        )

        return (true_lat + lat_jump, true_lon + lon_jump)
