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
Blade Element Momentum Theory (BEMT).

Reference:
    Leishman, J.G. (2006). "Principles of Helicopter Aerodynamics"
    Cambridge University Press, 2nd Edition, Chapter 3

    Johnson, W. (2013). "Rotorcraft Aeromechanics"
    Cambridge University Press, Chapter 3

Theory:
    BEMT combines momentum theory (momentum conservation) with
    blade element theory (2D airfoil sections) to predict rotor
    thrust and power.

    Key equations:
        Thrust: T = CT × ρ × A × (Ω×R)²
        Power: P = CP × ρ × A × (Ω×R)³
        Figure of Merit: FM = T^(3/2) / (√(2ρA) × P)
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class BladeGeometry:
    """
    Propeller blade geometry parameters.

    Reference: Leishman (2006), Section 3.2
    """

    radius_m: float = 0.127  # 5-inch propeller
    chord_m: float = 0.015  # Mean aerodynamic chord
    num_blades: int = 2
    twist_deg: float = 15.0  # Root-to-tip twist
    root_cutout: float = 0.1  # Non-lifting root region (fraction)

    @property
    def disk_area_m2(self) -> float:
        """Rotor disk area (m²)."""
        return math.pi * self.radius_m**2

    @property
    def solidity(self) -> float:
        """
        Rotor solidity σ = Nc/(πR).

        Reference: Leishman (2006), Eq. 3.8
        """
        return self.num_blades * self.chord_m / (math.pi * self.radius_m)


@dataclass
class AirfoilData:
    """
    2D airfoil aerodynamic characteristics.

    Default values for NACA 0012 (symmetric, common for small rotors).

    Reference:
        Abbott & Von Doenhoff (1959), "Theory of Wing Sections"
        NACA Report R-824
    """

    cl_alpha: float = 5.73  # 2π ≈ 6.28 for thin airfoil theory, typical 5.7
    cl_max: float = 1.0  # Maximum lift coefficient
    cd_0: float = 0.008  # Zero-lift drag coefficient
    cd_stall: float = 0.3  # Post-stall drag
    alpha_stall_deg: float = 12.0  # Stall angle

    def get_cl(self, alpha_deg: float) -> float:
        """Lift coefficient at angle of attack."""
        alpha_rad = math.radians(alpha_deg)

        if abs(alpha_deg) < self.alpha_stall_deg:
            return self.cl_alpha * alpha_rad
        else:
            # Post-stall (Viterna model approximation)
            sign = 1.0 if alpha_deg > 0 else -1.0
            # Reduced lift after stall
            stall_factor = 0.7 * self.cl_max
            return sign * stall_factor

    def get_cd(self, alpha_deg: float) -> float:
        """Drag coefficient at angle of attack."""
        if abs(alpha_deg) < self.alpha_stall_deg:
            # Quadratic drag polar: CD = CD0 + CL²/(π×AR×e)
            cl = self.get_cl(alpha_deg)
            return self.cd_0 + cl**2 / (math.pi * 6.0 * 0.85)  # AR≈6, e≈0.85
        else:
            return self.cd_stall


class BladeElementMomentumTheory:
    """
    Blade Element Momentum Theory for multirotor propellers.

    Reference:
        Leishman (2006), Chapter 3
        Johnson (2013), Chapter 3

    Combines:
        - Momentum theory: Global momentum balance
        - Blade element: Local 2D aerodynamics

    Example:
        >>> bemt = BladeElementMomentumTheory()
        >>> thrust, power = bemt.calculate_performance(rpm=10000, rho=1.225)
        >>> print(f"Thrust: {thrust:.2f} N, Power: {power:.2f} W")
    """

    def __init__(
        self,
        blade: Optional[BladeGeometry] = None,
        airfoil: Optional[AirfoilData] = None,
        num_elements: int = 20,
    ) -> None:
        """
        Initialize BEMT calculator.

        Args:
            blade: Blade geometry (default: 5-inch propeller)
            airfoil: 2D airfoil data (default: NACA 0012)
            num_elements: Number of blade elements for integration
        """
        self.blade = blade or BladeGeometry()
        self.airfoil = airfoil or AirfoilData()
        self.num_elements = num_elements

    def calculate_ct(
        self, rpm: float, rho: float, axial_velocity: float = 0.0
    ) -> float:
        """
        Calculate thrust coefficient CT.

        Reference: Leishman (2006), Eq. 3.47

        CT = T / (ρ × A × Ω²R²)

        Args:
            rpm: Rotational speed (rev/min)
            rho: Air density (kg/m³)
            axial_velocity: Axial inflow velocity (m/s)

        Returns:
            Thrust coefficient CT (dimensionless)
        """
        omega = rpm * 2 * math.pi / 60  # rad/s
        tip_speed = omega * self.blade.radius_m

        if tip_speed < 1.0:
            return 0.0

        # Advance ratio (for axial flight)
        mu_z = axial_velocity / tip_speed

        # Simple BEMT: CT = (σ × a / 2) × (θ₀/3 + θ₁/4 - λ/2)
        # For hover (simplified):
        sigma = self.blade.solidity
        a = self.airfoil.cl_alpha
        theta_0 = math.radians(self.blade.twist_deg / 2)  # Mean pitch

        # Induced inflow ratio (momentum theory)
        # λ = √(CT/2) for hover
        # Iterate to solve λ
        lambda_i = 0.0
        for _ in range(10):
            ct_est = sigma * a * (theta_0 / 3 - lambda_i / 2) / 2
            lambda_i = math.sqrt(abs(ct_est) / 2) if ct_est > 0 else 0

        return sigma * a * (theta_0 / 3 - lambda_i / 2) / 2

    def calculate_thrust(
        self,
        rpm: float,
        rho: float = 1.225,
        axial_velocity: float = 0.0,
    ) -> float:
        """
        Calculate rotor thrust.

        Reference: Leishman (2006), Eq. 3.15

        T = CT × ρ × A × (Ω×R)²

        Args:
            rpm: Rotational speed (rev/min)
            rho: Air density (kg/m³)
            axial_velocity: Axial inflow (m/s)

        Returns:
            Thrust (N)
        """
        omega = rpm * 2 * math.pi / 60
        tip_speed = omega * self.blade.radius_m
        A = self.blade.disk_area_m2
        CT = self.calculate_ct(rpm, rho, axial_velocity)

        return CT * rho * A * tip_speed**2

    def calculate_power(self, rpm: float, rho: float = 1.225) -> float:
        """
        Calculate rotor power.

        Reference: Leishman (2006), Eq. 3.65

        P = CP × ρ × A × (Ω×R)³

        Components:
            P = P_induced + P_profile
            P_induced = T × v_i (induced velocity)
            P_profile = (σ × CD₀ / 8) × ρ × A × (Ω×R)³

        Args:
            rpm: Rotational speed (rev/min)
            rho: Air density (kg/m³)

        Returns:
            Power (W)
        """
        omega = rpm * 2 * math.pi / 60
        tip_speed = omega * self.blade.radius_m
        A = self.blade.disk_area_m2
        T = self.calculate_thrust(rpm, rho)

        if T <= 0 or tip_speed < 1:
            return 0.0

        # Induced power (momentum theory)
        # P_i = T × v_i = T × √(T / (2ρA))
        v_i = math.sqrt(T / (2 * rho * A))
        P_induced = T * v_i

        # Profile power
        # P_0 = (σ × CD₀ / 8) × ρ × A × (Ω×R)³
        sigma = self.blade.solidity
        cd_0 = self.airfoil.cd_0
        P_profile = (sigma * cd_0 / 8) * rho * A * tip_speed**3

        return P_induced + P_profile

    def calculate_figure_of_merit(self, rpm: float, rho: float = 1.225) -> float:
        """
        Calculate Figure of Merit (FM).

        Reference: Leishman (2006), Eq. 3.75

        FM = P_ideal / P_actual = T^(3/2) / (√(2ρA) × P)

        Perfect rotor has FM = 1.0
        Good rotor has FM > 0.7

        Args:
            rpm: Rotational speed (rev/min)
            rho: Air density (kg/m³)

        Returns:
            Figure of Merit (0 to 1)
        """
        T = self.calculate_thrust(rpm, rho)
        P = self.calculate_power(rpm, rho)
        A = self.blade.disk_area_m2

        if T <= 0 or P <= 0:
            return 0.0

        P_ideal = T**1.5 / math.sqrt(2 * rho * A)
        return min(1.0, P_ideal / P)

    def calculate_performance(
        self,
        rpm: float,
        rho: float = 1.225,
        axial_velocity: float = 0.0,
    ) -> Tuple[float, float, float]:
        """
        Calculate complete performance.

        Args:
            rpm: Rotational speed
            rho: Air density
            axial_velocity: Climb rate

        Returns:
            (thrust_N, power_W, figure_of_merit)
        """
        thrust = self.calculate_thrust(rpm, rho, axial_velocity)
        power = self.calculate_power(rpm, rho)
        fm = self.calculate_figure_of_merit(rpm, rho)

        return (thrust, power, fm)
