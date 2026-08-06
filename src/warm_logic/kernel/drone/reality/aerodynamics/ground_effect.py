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
Ground Effect and Wall Effect Models.

Reference:
    Cheeseman, I.C. & Bennett, W.E. (1955). "The Effect of Ground on a
    Helicopter Rotor in Forward Flight" ARC R&M 3021

    Hayden, J.S. (1976). "The Effect of the Ground on Helicopter Hovering
    Power Required" AHS 32nd Annual Forum

    Fradenburgh, E.A. (1972). "The Helicopter and the Ground Effect Machine"
    Journal of the AHS, Vol. 17, No. 4

Theory:
    Ground effect increases thrust (or reduces power) when a rotor
    operates near the ground. The downwash is partially blocked,
    reducing induced velocity and thus induced power.
"""

import math
from dataclasses import dataclass


@dataclass
class GroundEffect:
    """
    Ground Effect Model for Rotorcraft.

    Reference:
        Cheeseman & Bennett (1955), Eq. 1-3
        Hayden (1976), Eq. 5

    The ground effect increases thrust by reducing induced velocity.
    The effect depends on the ratio of height to rotor radius (z/R).

    Key equation (Cheeseman-Bennett):
        T_IGE/T_OGE = 1 / (1 - (R/4z)²)

    Where:
        T_IGE = Thrust in ground effect
        T_OGE = Thrust out of ground effect
        R = Rotor radius
        z = Height above ground

    Example:
        >>> ge = GroundEffect(rotor_radius_m=0.127)
        >>> multiplier = ge.get_thrust_ratio(altitude_m=0.1)
        >>> print(f"Thrust increase: {(multiplier-1)*100:.1f}%")
    """

    rotor_radius_m: float = 0.127  # 5-inch propeller

    def get_thrust_ratio(self, altitude_m: float) -> float:
        """
        Calculate thrust ratio T_IGE/T_OGE.

        Reference: Cheeseman & Bennett (1955), Eq. 2

        Args:
            altitude_m: Height above ground (m)

        Returns:
            Thrust ratio (>1 means increased thrust)
        """
        R = self.rotor_radius_m
        z = max(0.01, altitude_m)  # Prevent division by zero

        # Height/radius ratio
        z_R = z / R

        if z_R > 4.0:
            # Out of ground effect region
            return 1.0

        # Cheeseman-Bennett formula
        # T_IGE/T_OGE = 1 / (1 - (R/4z)²) = 1 / (1 - 1/(4×z/R)²)
        term = 1.0 / (4.0 * z_R)
        ratio = 1.0 / (1.0 - term**2)

        # Limit to physically reasonable range
        return min(1.5, max(1.0, ratio))

    def get_power_ratio(self, altitude_m: float) -> float:
        """
        Calculate power ratio P_IGE/P_OGE.

        Reference: Hayden (1976), Eq. 8

        For constant thrust, power in ground effect is reduced.

        Args:
            altitude_m: Height above ground (m)

        Returns:
            Power ratio (<1 means reduced power)
        """
        thrust_ratio = self.get_thrust_ratio(altitude_m)

        # For constant thrust: P_IGE/P_OGE = 1/√(T_ratio)
        # (Simplified from induced power relation)
        return 1.0 / math.sqrt(thrust_ratio)


@dataclass
class WallEffect:
    """
    Wall Effect Model for Multirotors.

    Reference:
        Mahony, R. et al. (2012). "Multirotor Aerial Vehicles:
        Modeling, Estimation, and Control of Quadrotor"
        IEEE Robotics & Automation Magazine

    When a rotor operates near a vertical wall, the wake is
    deflected causing a lateral force and yaw moment.

    The wall effect is less studied than ground effect but
    can cause significant disturbance during indoor flight.
    """

    rotor_radius_m: float = 0.127

    def get_lateral_force_coefficient(self, wall_distance_m: float) -> float:
        """
        Estimate lateral force coefficient due to wall.

        Reference: Empirical model based on CFD studies

        Args:
            wall_distance_m: Distance to wall (m)

        Returns:
            Force coefficient (fraction of hover thrust)
        """
        R = self.rotor_radius_m
        d = max(0.01, wall_distance_m)

        d_R = d / R

        if d_R > 3.0:
            return 0.0

        # Empirical model: exponential decay
        # C_wall ≈ 0.1 × exp(-d/R)
        return 0.1 * math.exp(-d_R)
