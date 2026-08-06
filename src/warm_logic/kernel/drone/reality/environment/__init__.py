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
"""Environment Models."""

import math
from dataclasses import dataclass


@dataclass
class PlanetaryPhysics:
    """WGS84 Gravity and Coriolis. Reference: WGS84 Technical Report."""

    def gravity_at_location(self, lat_deg: float, alt_m: float) -> float:
        """Local gravity (Somigliana formula + free-air correction)."""
        lat_rad = math.radians(lat_deg)
        sin_lat_sq = math.sin(lat_rad) ** 2

        # WGS84 Somigliana
        g_sea = (
            9.7803253359
            / math.sqrt(1 - 0.00669437999014 * sin_lat_sq)
        )

        # Free-air correction
        g = g_sea - 3.086e-6 * alt_m
        return g

    def coriolis_acceleration(self, lat_deg: float, velocity_ned: tuple) -> tuple:
        """Coriolis acceleration (2×Ω×v). Reference: Goldstein Classical Mechanics."""
        omega = 7.292115e-5  # Earth rotation rad/s
        lat_rad = math.radians(lat_deg)
        vn, ve, vd = velocity_ned

        ac_n = 2 * omega * (ve * math.sin(lat_rad))
        ac_e = -2 * omega * (vn * math.sin(lat_rad) + vd * math.cos(lat_rad))
        ac_d = 2 * omega * (ve * math.cos(lat_rad))

        return (ac_n, ac_e, ac_d)
