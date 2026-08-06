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
BLDC Motor and ESC Models.

Reference:
    Krishnan, R. (2010). "Permanent Magnet Synchronous and Brushless DC
    Motor Drives" CRC Press

    Hughes, A. & Drury, B. (2019). "Electric Motors and Drives:
    Fundamentals, Types and Applications" 5th Edition, Newnes
"""

import math
from dataclasses import dataclass


@dataclass
class BLDCMotor:
    """
    Brushless DC Motor Model.

    Reference:
        Krishnan (2010), Chapter 8
        Hughes & Drury (2019), Chapter 11

    Key parameters:
        Kv: Motor velocity constant (RPM/V)
        Kt: Torque constant (N·m/A) = 60/(2π×Kv)
        Rm: Winding resistance (Ω)
        I0: No-load current (A)

    Equations:
        RPM = Kv × V_applied
        Torque = Kt × (I - I0)
        Power_mech = ω × Torque
        Efficiency = P_mech / (V × I)

    Example:
        >>> motor = BLDCMotor(kv=920)
        >>> rpm, current, efficiency = motor.calculate_operating_point(
        ...     voltage=14.8, load_torque=0.05
        ... )
    """

    # Motor constants
    kv: float = 920  # RPM/V (typical 5-inch drone motor)
    rm: float = 0.1  # Winding resistance (Ω)
    i0: float = 0.8  # No-load current (A)

    # Mechanical properties
    rotor_inertia_kg_m2: float = 1e-5
    friction_torque_nm: float = 0.001

    @property
    def kt(self) -> float:
        """Torque constant (N·m/A)."""
        # Kt = 60 / (2π × Kv) = 9.55 / Kv
        return 9.55 / self.kv

    @property
    def ke(self) -> float:
        """Back-EMF constant (V/rad/s)."""
        # For ideal motor: Ke = Kt
        return self.kt

    def get_back_emf(self, rpm: float) -> float:
        """
        Calculate back-EMF voltage.

        Reference: Krishnan (2010), Eq. 8.5

        E = Ke × ω = V_applied / Kv × RPM

        Args:
            rpm: Motor speed (rev/min)

        Returns:
            Back-EMF voltage (V)
        """
        omega = rpm * 2 * math.pi / 60
        return self.ke * omega

    def calculate_operating_point(
        self,
        voltage: float,
        load_torque: float,
    ) -> tuple:
        """
        Calculate steady-state operating point.

        Reference: Hughes & Drury (2019), Section 11.4

        At steady state:
            V = E + I×Rm
            Torque = Kt × I = Load_torque

        Args:
            voltage: Applied voltage (V)
            load_torque: Mechanical load torque (N·m)

        Returns:
            (rpm, current, efficiency)
        """
        # Required current for torque
        i_load = load_torque / self.kt + self.i0

        # Back-EMF at operating point
        e = voltage - i_load * self.rm

        if e <= 0:
            return (0.0, self.i0, 0.0)

        # RPM from back-EMF
        rpm = e * self.kv

        # Power calculations
        power_elec = voltage * i_load
        power_mech = load_torque * (rpm * 2 * math.pi / 60)
        efficiency = power_mech / power_elec if power_elec > 0 else 0

        return (rpm, i_load, efficiency)

    def get_max_rpm(self, voltage: float) -> float:
        """
        Maximum no-load RPM at given voltage.

        Args:
            voltage: Applied voltage (V)

        Returns:
            Max RPM
        """
        # Account for no-load current IR drop
        effective_v = voltage - self.i0 * self.rm
        return max(0, effective_v * self.kv)


@dataclass
class ESCModel:
    """
    Electronic Speed Controller Model.

    Reference:
        Kim, H.S. et al. (2017). "Sensorless BLDC Motor Drive with
        Adaptive PWM Control" IEEE Transactions

    Models:
        - PWM to voltage conversion
        - Switching losses
        - Current limiting
    """

    # ESC properties
    max_current_a: float = 30.0
    pwm_frequency_hz: float = 24000.0  # Typical drone ESC
    dead_time_ns: float = 1000.0  # Switching dead time
    mosfet_rds_on: float = 0.002  # MOSFET on-resistance

    # Throttle response
    min_throttle: float = 0.05  # Arm threshold
    max_throttle: float = 1.0

    def get_output_voltage(self, throttle: float, bus_voltage: float) -> float:
        """
        Convert throttle command to effective voltage.

        Args:
            throttle: Throttle command (0 to 1)
            bus_voltage: Battery voltage (V)

        Returns:
            Effective motor voltage (V)
        """
        # Clamp throttle
        throttle = max(0, min(1, throttle))

        if throttle < self.min_throttle:
            return 0.0

        # Linear mapping with dead time loss
        duty = (throttle - self.min_throttle) / (self.max_throttle - self.min_throttle)
        dead_time_loss = self.dead_time_ns * 1e-9 * self.pwm_frequency_hz * 2

        effective_duty = duty * (1 - dead_time_loss)

        return bus_voltage * effective_duty

    def get_switching_losses(self, current_a: float) -> float:
        """
        Calculate switching power losses.

        Reference: Kim et al. (2017), Section III

        Args:
            current_a: Motor current (A)

        Returns:
            Power loss (W)
        """
        # Conduction losses
        p_conduction = current_a**2 * self.mosfet_rds_on * 6  # 6 MOSFETs

        # Switching losses (simplified)
        p_switching = current_a * 0.01 * self.pwm_frequency_hz / 1000

        return p_conduction + p_switching

    def limit_current(self, requested_current: float) -> float:
        """
        Apply current limiting.

        Args:
            requested_current: Requested current (A)

        Returns:
            Allowed current (A)
        """
        return min(requested_current, self.max_current_a)
