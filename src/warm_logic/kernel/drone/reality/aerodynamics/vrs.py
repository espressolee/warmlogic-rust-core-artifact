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
Vortex Ring State (VRS) Model.

Reference:
    Johnson, W. (1980). "Helicopter Theory" Princeton University Press,
    Chapter 5, Section 5.3

    Brand, A.G. et al. (1987). "Vortex Ring State Entry and Flight Test
    Results" AHS 43rd Annual Forum

    Newman, S.J. et al. (2001). "A New Look at the Vortex Ring State"
    AHS 57th Annual Forum

Theory:
    Vortex Ring State occurs when a rotor descends into its own wake.
    The induced flow recirculates around the rotor disk forming a
    toroidal vortex "ring" that traps the rotor.

    VRS entry conditions (Johnson criterion):
        V_descent > 0.7 × v_h  (descent rate exceeds ~70% of hover induced)
        V_forward < 1.5 × v_h  (low forward speed)

    Where v_h = √(T/(2ρA)) is the hover induced velocity.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class VRSState(Enum):
    """VRS operational state."""

    CLEAR = "clear"  # Normal operation
    ONSET = "onset"  # Approaching VRS
    DEVELOPED = "developed"  # In VRS
    WINDMILL_BRAKE = "windmill_brake"  # Descended through VRS


@dataclass
class VortexRingState:
    """
    Vortex Ring State Detection and Effects.

    Reference:
        Johnson (1980), Section 5.3
        Newman et al. (2001)

    VRS is characterized by:
        - Rapid power increase with no altitude gain
        - Thrust fluctuations (15-30% oscillations)
        - Severe vibrations
        - Loss of collective pitch effectiveness

    Recovery:
        - Increase forward speed (>30 kt)
        - Lower collective (descend through VRS)
        - Autorotation entry

    Example:
        >>> vrs = VortexRingState(rotor_radius_m=0.127)
        >>> state = vrs.check_state(v_descent=3.0, v_forward=1.0, thrust=5.0, rho=1.225)
        >>> print(f"VRS State: {state.value}")
    """

    rotor_radius_m: float = 0.127
    rotor_disk_area_m2: Optional[float] = None

    def __post_init__(self) -> None:
        if self.rotor_disk_area_m2 is None:
            self.rotor_disk_area_m2 = math.pi * self.rotor_radius_m**2

    def get_hover_induced_velocity(self, thrust_n: float, rho: float) -> float:
        """
        Calculate hover induced velocity v_h.

        Reference: Johnson (1980), Eq. 2.8

        v_h = √(T/(2ρA))

        Args:
            thrust_n: Rotor thrust (N)
            rho: Air density (kg/m³)

        Returns:
            Induced velocity (m/s)
        """
        if thrust_n <= 0:
            return 0.0
        return math.sqrt(thrust_n / (2 * rho * self.rotor_disk_area_m2))

    def check_state(
        self,
        v_descent_m_s: float,
        v_forward_m_s: float,
        thrust_n: float,
        rho: float = 1.225,
    ) -> VRSState:
        """
        Determine current VRS state.

        Reference: Johnson (1980) VRS boundary

        VRS Boundary:
            0.7 < V_d/v_h < 1.7 (descent)
            V_f/v_h < 1.5 (forward)

        Args:
            v_descent_m_s: Descent rate (positive = descending)
            v_forward_m_s: Forward velocity magnitude
            thrust_n: Current thrust
            rho: Air density

        Returns:
            Current VRS state
        """
        v_h = self.get_hover_induced_velocity(thrust_n, rho)

        if v_h < 0.1:
            return VRSState.CLEAR

        # Normalized velocities
        v_d_norm = v_descent_m_s / v_h
        v_f_norm = v_forward_m_s / v_h

        # Johnson VRS boundary
        if v_d_norm > 1.7:
            return VRSState.WINDMILL_BRAKE
        elif v_d_norm > 0.7 and v_f_norm < 1.5:
            if v_d_norm > 1.0:
                return VRSState.DEVELOPED
            else:
                return VRSState.ONSET
        else:
            return VRSState.CLEAR

    def get_thrust_reduction(
        self,
        v_descent_m_s: float,
        v_forward_m_s: float,
        thrust_n: float,
        rho: float = 1.225,
    ) -> float:
        """
        Calculate thrust reduction factor in VRS.

        Reference: Newman et al. (2001), Figure 5

        In developed VRS, effective thrust can drop to 30-60% of nominal.

        Args:
            v_descent_m_s: Descent rate
            v_forward_m_s: Forward velocity
            thrust_n: Nominal thrust
            rho: Air density

        Returns:
            Thrust multiplier (1.0 = no reduction)
        """
        state = self.check_state(v_descent_m_s, v_forward_m_s, thrust_n, rho)

        if state == VRSState.CLEAR:
            return 1.0
        elif state == VRSState.ONSET:
            return 0.85  # 15% reduction
        elif state == VRSState.DEVELOPED:
            return 0.40  # 60% reduction (severe!)
        else:  # WINDMILL_BRAKE
            return 0.20  # Almost no thrust

    def get_vibration_level(
        self,
        v_descent_m_s: float,
        v_forward_m_s: float,
        thrust_n: float,
        rho: float = 1.225,
    ) -> float:
        """
        Estimate vibration level in VRS.

        Reference: Brand et al. (1987)

        VRS causes severe vibrations due to asymmetric vortex shedding.

        Args:
            v_descent_m_s: Descent rate
            v_forward_m_s: Forward velocity
            thrust_n: Nominal thrust
            rho: Air density

        Returns:
            Vibration multiplier (1.0 = normal, up to 10.0 in VRS)
        """
        state = self.check_state(v_descent_m_s, v_forward_m_s, thrust_n, rho)

        vibration_levels = {
            VRSState.CLEAR: 1.0,
            VRSState.ONSET: 3.0,
            VRSState.DEVELOPED: 10.0,
            VRSState.WINDMILL_BRAKE: 5.0,
        }

        return vibration_levels.get(state, 1.0)
