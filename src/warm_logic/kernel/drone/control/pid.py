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
Robust PID Controller.

Features:
- Anti-windup (Clamping)
- Derivative Filter (Low Pass)
- Feedforward Term
"""

from dataclasses import dataclass, field
from typing import Optional

from .filter import LowPassFilter


@dataclass
class RobustPID:
    """
    PID Controller with robustness features.

    u(t) = Kp * e(t) + Ki * int(e(t)) + Kd * de(t)/dt + FF
    """

    kp: float
    ki: float
    kd: float
    dt: float

    # Limits
    output_min: float = -1.0
    output_max: float = 1.0
    integrator_min: float = -0.5
    integrator_max: float = 0.5

    # Derivative Filter
    d_term_filter_hz: float = 20.0

    # State
    _integrator: float = 0.0
    _prev_error: float = 0.0
    _d_filter: Optional[LowPassFilter] = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.d_term_filter_hz > 0:
            self._d_filter = LowPassFilter(
                cutoff_freq_hz=self.d_term_filter_hz, dt=self.dt
            )

    def update(self, error: float, feedforward: float = 0.0) -> float:
        """
        Calculate PID output.

        Args:
            error: Setpoint - Measurement
            feedforward: Feedforward term (e.g. gravity compensation)

        Returns:
            Control output (u)
        """
        # P Term
        p_term = self.kp * error

        # I Term (with anti-windup clamping)
        self._integrator += self.ki * error * self.dt

        # Clamp integrator
        if self._integrator > self.integrator_max:
            self._integrator = self.integrator_max
        elif self._integrator < self.integrator_min:
            self._integrator = self.integrator_min

        i_term = self._integrator

        # D Term (Filtered)
        derivative = (error - self._prev_error) / self.dt
        if self._d_filter:
            derivative = self._d_filter.update(derivative)

        d_term = self.kd * derivative

        # Total Output
        output = p_term + i_term + d_term + feedforward

        # Output Saturation
        if output > self.output_max:
            output = self.output_max
        elif output < self.output_min:
            output = self.output_min

        # Update State
        self._prev_error = error

        return output

    def reset(self) -> None:
        """Reset internal state."""
        self._integrator = 0.0
        self._prev_error = 0.0
        if self._d_filter:
            self._d_filter.reset()
