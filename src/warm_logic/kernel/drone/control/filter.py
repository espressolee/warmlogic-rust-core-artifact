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
Signal Processing Filters for Drone Control.

Implements digital filters to remove sensor noise and mechanical vibrations.
Reference:
- Notch Filter: Oppenheim & Schafer, Discrete-Time Signal Processing
- Low Pass: 1st Order RC Filter Discretization
"""

import math
from dataclasses import dataclass, field


@dataclass
class LowPassFilter:
    """
    1st Order Low Pass Filter.

    Smooths out high-frequency noise.
    y[n] = alpha * x[n] + (1 - alpha) * y[n-1]
    """

    cutoff_freq_hz: float
    dt: float
    _alpha: float = field(init=False)
    _prev_output: float = 0.0

    def __post_init__(self) -> None:
        self._calculate_alpha()

    def _calculate_alpha(self) -> None:
        if self.cutoff_freq_hz <= 0 or self.dt <= 0:
            self._alpha = 1.0
            return

        rc = 1.0 / (2.0 * math.pi * self.cutoff_freq_hz)
        self._alpha = self.dt / (self.dt + rc)

    def update(self, input_val: float) -> float:
        """Apply filter to new input."""
        output = self._alpha * input_val + (1.0 - self._alpha) * self._prev_output
        self._prev_output = output
        return output

    def reset(self, initial_value: float = 0.0) -> None:
        """Reset filter state."""
        self._prev_output = initial_value


@dataclass
class NotchFilter:
    """
    2nd Order IIR Notch Filter.

    Removes a specific frequency (e.g., motor vibration).
    Discretized using Bilinear Transform (Tustin).
    """

    center_freq_hz: float
    bandwidth_hz: float
    sampling_freq_hz: float

    # Coefficients
    _a0: float = 1.0
    _a1: float = 0.0
    _a2: float = 0.0
    _b0: float = 1.0
    _b1: float = 0.0
    _b2: float = 0.0

    # State history
    _x1: float = 0.0
    _x2: float = 0.0
    _y1: float = 0.0
    _y2: float = 0.0

    def __post_init__(self) -> None:
        self._calculate_coefficients()

    def _calculate_coefficients(self) -> None:
        """Calculate IIR coefficients."""
        if self.center_freq_hz <= 0 or self.sampling_freq_hz <= 0:
            # Pass-through
            self._b0, self._b1, self._b2 = 1.0, 0.0, 0.0
            self._a0, self._a1, self._a2 = 1.0, 0.0, 0.0
            return

        omega = 2.0 * math.pi * self.center_freq_hz / self.sampling_freq_hz
        width = 2.0 * math.pi * self.bandwidth_hz / self.sampling_freq_hz

        # Pre-warped frequency
        # For simplicity in implementation using matched Z-transform approximation
        # or standard direct form II design

        # Using standard coefficients for notch
        beta = math.cos(omega)
        alpha = math.sin(width) / 2.0  # approximate Q factor relation

        # High Q notch
        gain = 1.0  # Unity gain at DC and Nyquist

        # Coefficients
        b0 = 1.0
        b1 = -2.0 * beta
        b2 = 1.0
        a0 = 1.0 + alpha
        a1 = -2.0 * beta
        a2 = 1.0 - alpha

        # Normalize by a0
        self._b0 = b0 / a0
        self._b1 = b1 / a0
        self._b2 = b2 / a0
        self._a1 = a1 / a0
        self._a2 = a2 / a0

    def update(self, input_val: float) -> float:
        """Apply notch filter (Direct Form I)."""
        output = (
            self._b0 * input_val
            + self._b1 * self._x1
            + self._b2 * self._x2
            - self._a1 * self._y1
            - self._a2 * self._y2
        )

        # Shift history
        self._x2 = self._x1
        self._x1 = input_val
        self._y2 = self._y1
        self._y1 = output

        return output

    def reset(self) -> None:
        """Reset filter state."""
        self._x1 = self._x2 = self._y1 = self._y2 = 0.0
