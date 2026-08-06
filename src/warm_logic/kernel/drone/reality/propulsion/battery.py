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
Battery Models.

Reference:
    Zhang, L. et al. (2017). "A Simple and Effective Approach Based on
    Twin-Gauss to Refine the State of Charge of LiFePO4 Battery"
    Journal of Power Sources, Vol. 369

    Tremblay, O. & Dessaint, L.A. (2009). "Experimental Validation of a
    Battery Dynamic Model for EV Applications"
    World Electric Vehicle Journal, Vol. 3

    Peukert, W. (1897). "Über die Abhängigkeit der Kapazität von der
    Entladestromstärke bei Bleiakkumulatoren"
    Elektrotechnische Zeitschrift, Vol. 18

Theory:
    The Thevenin equivalent circuit models battery as:
    - OCV(SOC): Open circuit voltage as function of state of charge
    - R0: Series resistance (immediate voltage drop)
    - R1-C1: Short time constant RC pair
    - R2-C2: Long time constant RC pair
"""

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TheveninBattery:
    """
    2-RC Thevenin Equivalent Circuit Battery Model.

    Reference:
        Zhang et al. (2017), Section 2.1
        Tremblay & Dessaint (2009)

    Circuit:
        Vt = OCV(SOC) - I×R0 - V_RC1 - V_RC2

    Where:
        dV_RC1/dt = I/C1 - V_RC1/(R1×C1)
        dV_RC2/dt = I/C2 - V_RC2/(R2×C2)

    Example:
        >>> battery = TheveninBattery(capacity_ah=5.0, num_cells=4)
        >>> v_terminal = battery.get_terminal_voltage(current_a=20.0)
    """

    # Battery configuration
    capacity_ah: float = 5.0  # Nominal capacity
    num_cells: int = 4  # Series cell count (4S for typical drone)
    cell_chemistry: str = "LiPo"  # "LiPo", "Li-ion", "LiFePO4"

    # Series resistance (Ohm per cell)
    r0_ohm_per_cell: float = 0.012

    # RC time constants
    r1_ohm_per_cell: float = 0.008
    c1_farad: float = 5000.0  # Short time constant τ1 = R1×C1 ≈ 40s
    r2_ohm_per_cell: float = 0.005
    c2_farad: float = 50000.0  # Long time constant τ2 = R2×C2 ≈ 250s

    # State of charge (0 to 1)
    soc: float = 1.0

    # Internal states
    _v_rc1: float = field(default=0.0, repr=False)
    _v_rc2: float = field(default=0.0, repr=False)
    _temperature_c: float = field(default=25.0, repr=False)

    def get_ocv(self, soc: Optional[float] = None) -> float:
        """
        Open Circuit Voltage as function of SOC.

        Reference: Zhang et al. (2017), Eq. 3

        Uses polynomial fit for LiPo:
            OCV = a0 + a1×SOC + a2×SOC² + a3×SOC³

        Args:
            soc: State of charge (0 to 1)

        Returns:
            OCV per cell (V)
        """
        if soc is None:
            soc = self.soc

        soc = max(0, min(1, soc))

        if self.cell_chemistry == "LiPo":
            # LiPo polynomial coefficients (empirical fit)
            # Valid for 3.0V to 4.2V range
            a0 = 3.0
            a1 = 1.2
            a2 = -0.6
            a3 = 0.6

            ocv = a0 + a1 * soc + a2 * soc**2 + a3 * soc**3
            return max(3.0, min(4.2, ocv))

        elif self.cell_chemistry == "LiFePO4":
            # LiFePO4 has flat voltage curve
            if soc > 0.9:
                return 3.35 + 0.5 * (soc - 0.9)
            elif soc > 0.1:
                return 3.25 + 0.1 * (soc - 0.1) / 0.8
            else:
                return 2.5 + 0.75 * soc / 0.1

        else:  # Li-ion
            return 3.0 + 1.2 * soc

    @property
    def total_r0(self) -> float:
        """Total series resistance (Ohm)."""
        # Temperature effect: resistance increases at low temp
        temp_factor = 1.0 + max(0, (25 - self._temperature_c)) * 0.02
        return self.r0_ohm_per_cell * self.num_cells * temp_factor

    def get_terminal_voltage(self, current_a: float, dt: float = 0.0) -> float:
        """
        Calculate terminal voltage under load.

        Reference: Tremblay & Dessaint (2009), Eq. 1

        Vt = n × OCV(SOC) - I×R0 - V_RC1 - V_RC2

        Args:
            current_a: Discharge current (A, positive = discharge)
            dt: Time step for RC dynamics (s)

        Returns:
            Terminal voltage (V)
        """
        ocv = self.get_ocv() * self.num_cells

        # Immediate IR drop
        v_r0 = current_a * self.total_r0

        # RC dynamics update
        if dt > 0:
            r1 = self.r1_ohm_per_cell * self.num_cells
            r2 = self.r2_ohm_per_cell * self.num_cells

            tau1 = r1 * self.c1_farad
            tau2 = r2 * self.c2_farad

            alpha1 = math.exp(-dt / tau1) if tau1 > 0 else 0
            alpha2 = math.exp(-dt / tau2) if tau2 > 0 else 0

            self._v_rc1 = alpha1 * self._v_rc1 + r1 * (1 - alpha1) * current_a
            self._v_rc2 = alpha2 * self._v_rc2 + r2 * (1 - alpha2) * current_a

        return ocv - v_r0 - self._v_rc1 - self._v_rc2

    def update_soc(self, current_a: float, dt: float) -> None:
        """
        Update state of charge (Coulomb counting).

        Reference: Tremblay & Dessaint (2009), Eq. 5

        SOC(t) = SOC(0) - ∫I dt / Q

        Args:
            current_a: Discharge current (A)
            dt: Time step (s)
        """
        # Coulomb counting
        charge_ah = current_a * dt / 3600
        self.soc -= charge_ah / self.capacity_ah
        self.soc = max(0, min(1, self.soc))


@dataclass
class PeukertCapacity:
    """
    Peukert's Law for Capacity vs Discharge Rate.

    Reference:
        Peukert, W. (1897). Original paper (in German)
        Doerffel, D. & Sharkh, S.A. (2006). "A Critical Review of Using
        the Peukert Equation" Journal of Power Sources, Vol. 155

    Equation:
        C_p = I^n × t

    Where:
        C_p = Peukert capacity (constant)
        I = Discharge current
        t = Discharge time
        n = Peukert exponent (1.0-1.4 for LiPo)

    This means higher discharge rates give less usable capacity.
    """

    # Peukert exponent
    # n = 1.0: Ideal (no capacity loss at high current)
    # n = 1.1-1.2: LiPo
    # n = 1.2-1.4: Lead-acid
    peukert_exponent: float = 1.1

    # Rated capacity at rated current
    rated_capacity_ah: float = 5.0
    rated_current_a: float = 1.0  # Usually C/1 rate

    def get_effective_capacity(self, discharge_current_a: float) -> float:
        """
        Calculate effective capacity at given discharge rate.

        Reference: Doerffel & Sharkh (2006), Eq. 3

        C_eff = C_rated × (I_rated / I_actual)^(n-1)

        Args:
            discharge_current_a: Actual discharge current (A)

        Returns:
            Effective capacity (Ah)
        """
        if discharge_current_a <= 0:
            return self.rated_capacity_ah

        n = self.peukert_exponent
        ratio = self.rated_current_a / discharge_current_a

        return self.rated_capacity_ah * (ratio ** (n - 1))

    def get_runtime_hours(self, capacity_ah: float, current_a: float) -> float:
        """
        Calculate runtime at given current.

        Reference: Doerffel & Sharkh (2006), Eq. 5

        t = C_p / I^n

        Args:
            capacity_ah: Nominal capacity
            current_a: Discharge current

        Returns:
            Runtime (hours)
        """
        if current_a <= 0:
            return float("inf")

        # Peukert capacity
        c_p = self.rated_capacity_ah * (self.rated_current_a**self.peukert_exponent)

        return c_p / (current_a**self.peukert_exponent)
