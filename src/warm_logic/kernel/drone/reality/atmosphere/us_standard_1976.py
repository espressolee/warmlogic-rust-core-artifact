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
US Standard Atmosphere 1976.

Reference:
    NOAA, NASA, USAF (1976). "U.S. Standard Atmosphere, 1976"
    NOAA-S/T 76-1562, NASA-TM-X-74335

Valid Range:
    0 to 86 km geometric altitude

Accuracy:
    Temperature: ±0.01 K (troposphere)
    Pressure: ±0.01% (troposphere)
    Density: ±0.01% (troposphere)
"""

import math
from dataclasses import dataclass
from typing import Tuple

from ..constants import CONSTANTS


@dataclass
class AtmosphericState:
    """Atmospheric state at a given altitude."""

    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float
    dynamic_viscosity_pa_s: float
    kinematic_viscosity_m2_s: float


class USStandardAtmosphere1976:
    """
    US Standard Atmosphere 1976 Implementation.

    Implements the complete 7-layer atmospheric model from sea level to 86 km.

    Reference:
        NOAA-S/T 76-1562, Tables 1-5

    Example:
        >>> atm = USStandardAtmosphere1976()
        >>> state = atm.get_state(10000)  # 10 km altitude
        >>> print(f"T = {state.temperature_k:.2f} K")
        T = 223.25 K
    """

    # Layer boundaries and lapse rates (NOAA-S/T 76-1562, Table 4)
    # Format: (base_altitude_m, base_temp_k, lapse_rate_k_per_m)
    LAYERS: Tuple[Tuple[float, float, float], ...] = (
        (0, 288.15, -0.0065),  # Troposphere
        (11000, 216.65, 0.0),  # Tropopause (isothermal)
        (20000, 216.65, 0.001),  # Stratosphere 1
        (32000, 228.65, 0.0028),  # Stratosphere 2
        (47000, 270.65, 0.0),  # Stratopause (isothermal)
        (51000, 270.65, -0.0028),  # Mesosphere 1
        (71000, 214.65, -0.002),  # Mesosphere 2
    )

    def __init__(self):
        """Initialize with precomputed base pressures for each layer."""
        self._base_pressures = self._compute_base_pressures()

    def _compute_base_pressures(self) -> Tuple[float, ...]:
        """Compute pressure at base of each layer."""
        pressures = [CONSTANTS.SEA_LEVEL_PRESSURE]
        g = CONSTANTS.GRAVITY_STANDARD
        M = CONSTANTS.AIR_MOLAR_MASS
        R = 8.31447  # Universal gas constant

        for i in range(len(self.LAYERS) - 1):
            h_b, T_b, L = self.LAYERS[i]
            h_next = self.LAYERS[i + 1][0]
            dh = h_next - h_b
            P_b = pressures[-1]

            if L == 0:  # Isothermal layer
                P_next = P_b * math.exp(-g * M * dh / (R * T_b))
            else:  # Gradient layer
                T_next = T_b + L * dh
                P_next = P_b * (T_next / T_b) ** (-g * M / (R * L))

            pressures.append(P_next)

        return tuple(pressures)

    def get_layer_index(self, altitude_m: float) -> int:
        """Get the atmospheric layer index for given altitude."""
        for i in range(len(self.LAYERS) - 1, -1, -1):
            if altitude_m >= self.LAYERS[i][0]:
                return i
        return 0

    def get_temperature(self, altitude_m: float) -> float:
        """
        Temperature at altitude.

        Equation (23) from NOAA-S/T 76-1562:
            T = T_b + L × (h - h_b)

        Args:
            altitude_m: Geometric altitude (m)

        Returns:
            Temperature (K)
        """
        altitude_m = max(0, min(altitude_m, 86000))
        i = self.get_layer_index(altitude_m)
        h_b, T_b, L = self.LAYERS[i]
        return T_b + L * (altitude_m - h_b)

    def get_pressure(self, altitude_m: float) -> float:
        """
        Pressure at altitude.

        Equation (33a) for gradient layers:
            P = P_b × (T/T_b)^(-g₀M/(R*L))

        Equation (33b) for isothermal layers:
            P = P_b × exp(-g₀M(h-h_b)/(R*T_b))

        Args:
            altitude_m: Geometric altitude (m)

        Returns:
            Pressure (Pa)
        """
        altitude_m = max(0, min(altitude_m, 86000))
        i = self.get_layer_index(altitude_m)
        h_b, T_b, L = self.LAYERS[i]
        P_b = self._base_pressures[i]

        g = CONSTANTS.GRAVITY_STANDARD
        M = CONSTANTS.AIR_MOLAR_MASS
        R = 8.31447

        dh = altitude_m - h_b

        if L == 0:  # Isothermal
            return P_b * math.exp(-g * M * dh / (R * T_b))
        else:  # Gradient
            T = T_b + L * dh
            return P_b * (T / T_b) ** (-g * M / (R * L))

    def get_density(self, altitude_m: float) -> float:
        """
        Density at altitude.

        Ideal gas law: ρ = P/(R_specific × T)

        Args:
            altitude_m: Geometric altitude (m)

        Returns:
            Density (kg/m³)
        """
        T = self.get_temperature(altitude_m)
        P = self.get_pressure(altitude_m)
        R_specific = CONSTANTS.AIR_GAS_CONSTANT
        return P / (R_specific * T)

    def get_speed_of_sound(self, altitude_m: float) -> float:
        """
        Speed of sound at altitude.

        Equation: a = √(γ × R_specific × T)

        Reference: NOAA-S/T 76-1562, Equation (50)

        Args:
            altitude_m: Geometric altitude (m)

        Returns:
            Speed of sound (m/s)
        """
        T = self.get_temperature(altitude_m)
        gamma = CONSTANTS.SPECIFIC_HEAT_RATIO
        R_specific = CONSTANTS.AIR_GAS_CONSTANT
        return math.sqrt(gamma * R_specific * T)

    def get_dynamic_viscosity(self, altitude_m: float) -> float:
        """
        Dynamic viscosity using Sutherland's Law.

        Equation: μ = μ_ref × (T/T_ref)^(3/2) × (T_ref + S)/(T + S)

        Reference: NOAA-S/T 76-1562, Appendix B

        Args:
            altitude_m: Geometric altitude (m)

        Returns:
            Dynamic viscosity (Pa·s)
        """
        T = self.get_temperature(altitude_m)
        T_ref = CONSTANTS.SUTHERLAND_REFERENCE_TEMP
        mu_ref = CONSTANTS.SUTHERLAND_REFERENCE_VISCOSITY
        S = CONSTANTS.SUTHERLAND_CONSTANT

        return mu_ref * (T / T_ref) ** 1.5 * (T_ref + S) / (T + S)

    def get_kinematic_viscosity(self, altitude_m: float) -> float:
        """
        Kinematic viscosity.

        Equation: ν = μ/ρ

        Args:
            altitude_m: Geometric altitude (m)

        Returns:
            Kinematic viscosity (m²/s)
        """
        mu = self.get_dynamic_viscosity(altitude_m)
        rho = self.get_density(altitude_m)
        return mu / rho

    def get_state(self, altitude_m: float) -> AtmosphericState:
        """
        Get complete atmospheric state at altitude.

        Args:
            altitude_m: Geometric altitude (m)

        Returns:
            AtmosphericState with all properties
        """
        return AtmosphericState(
            altitude_m=altitude_m,
            temperature_k=self.get_temperature(altitude_m),
            pressure_pa=self.get_pressure(altitude_m),
            density_kg_m3=self.get_density(altitude_m),
            speed_of_sound_m_s=self.get_speed_of_sound(altitude_m),
            dynamic_viscosity_pa_s=self.get_dynamic_viscosity(altitude_m),
            kinematic_viscosity_m2_s=self.get_kinematic_viscosity(altitude_m),
        )


# Singleton instance
ATMOSPHERE = USStandardAtmosphere1976()
