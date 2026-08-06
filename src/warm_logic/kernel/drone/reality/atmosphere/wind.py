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
Wind Turbulence Models.

Implementations of MIL-SPEC atmospheric turbulence models
for flight simulation.

References:
    [1] MIL-F-8785C (1980), "Flying Qualities of Piloted Airplanes"
    [2] MIL-HDBK-1797 (1997), "Flying Qualities of Piloted Aircraft"
    [3] Dryden (1943), "A Mathematical Representation of Turbulence"
    [4] Von Karman (1948), "Progress in Statistical Theory of Turbulence"
"""

import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple


@dataclass
class DrydenTurbulence:
    """
    Dryden Wind Turbulence Model.

    Reference:
        MIL-F-8785C Section 3.7.5
        MIL-HDBK-1797 Section 3.7.11

    The Dryden model uses rational transfer functions to generate
    turbulence with specified intensity and scale length.

    Power Spectral Density (PSD):
        Φ_u(ω) = σ_u² × (2L_u/V) / (1 + (L_u×ω/V)²)

    Attributes:
        altitude_m: Altitude above ground level (m)
        airspeed_m_s: True airspeed (m/s)
        turbulence_intensity: 'light', 'moderate', 'severe'

    Example:
        >>> dryden = DrydenTurbulence(altitude_m=100, airspeed_m_s=20)
        >>> u, v, w = dryden.sample(dt=0.01)
    """

    altitude_m: float = 100.0
    airspeed_m_s: float = 20.0
    turbulence_intensity: str = "moderate"
    rng: Optional[Any] = None  # Optional RNG for deterministic behavior

    # Internal filter states
    _u_state: float = field(default=0.0, repr=False)
    _v_state: float = field(default=0.0, repr=False)
    _w_state: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        self._update_parameters()

    def _gauss(self, mu: float, sigma: float) -> float:
        """Generate Gaussian random number using RNG if available."""
        if self.rng is not None and hasattr(self.rng, "gauss"):
            return self.rng.gauss(mu, sigma)
        return random.gauss(mu, sigma)

    def _update_parameters(self) -> None:
        """Compute scale lengths and intensities (MIL-F-8785C Table VI)."""
        h = self.altitude_m

        # Scale lengths (MIL-F-8785C Section 3.7.5.1)
        if h < 304.8:  # Below 1000 ft
            self.L_u = h / 0.177**0.4
            self.L_v = self.L_u
            self.L_w = h
        else:  # Above 1000 ft
            self.L_u = 533.4  # 1750 ft
            self.L_v = 533.4
            self.L_w = 533.4

        # Turbulence intensity (MIL-F-8785C Table VII)
        W20 = self._get_wind_speed_at_20ft()

        if h < 304.8:  # Low altitude
            self.sigma_w = 0.1 * W20
            self.sigma_u = self.sigma_w / (0.177 + 0.000823 * h) ** 0.4
            self.sigma_v = self.sigma_u
        else:  # High altitude
            intensities = {"light": 0.5, "moderate": 1.5, "severe": 3.0}
            base = intensities.get(self.turbulence_intensity, 1.5)
            self.sigma_u = base
            self.sigma_v = base
            self.sigma_w = base

    def _get_wind_speed_at_20ft(self) -> float:
        """Wind speed at 20ft (MIL-F-8785C Table VII)."""
        intensities = {"light": 7.7, "moderate": 15.4, "severe": 23.2}  # m/s
        return intensities.get(self.turbulence_intensity, 15.4)

    def sample(self, dt: float) -> Tuple[float, float, float]:
        """
        Sample turbulence velocities using first-order filters.

        Reference:
            MIL-HDBK-1797 Equations 3.148-3.150

        Args:
            dt: Time step (s)

        Returns:
            (u, v, w) turbulence velocities in body frame (m/s)
        """
        V = max(1.0, self.airspeed_m_s)

        # Time constants
        tau_u = self.L_u / V
        tau_v = self.L_v / V
        tau_w = self.L_w / V

        # Filter coefficients (first-order)
        alpha_u = math.exp(-dt / tau_u) if tau_u > 0 else 0
        alpha_v = math.exp(-dt / tau_v) if tau_v > 0 else 0
        alpha_w = math.exp(-dt / tau_w) if tau_w > 0 else 0

        # White noise inputs (use deterministic RNG if provided)
        noise_u = self._gauss(0, 1) * math.sqrt(2 / tau_u) if tau_u > 0 else 0
        noise_v = self._gauss(0, 1) * math.sqrt(2 / tau_v) if tau_v > 0 else 0
        noise_w = self._gauss(0, 1) * math.sqrt(2 / tau_w) if tau_w > 0 else 0

        # First-order filter update
        self._u_state = alpha_u * self._u_state + (1 - alpha_u) * self.sigma_u * noise_u
        self._v_state = alpha_v * self._v_state + (1 - alpha_v) * self.sigma_v * noise_v
        self._w_state = alpha_w * self._w_state + (1 - alpha_w) * self.sigma_w * noise_w

        return (self._u_state, self._v_state, self._w_state)

    def reset(self) -> None:
        """Reset filter states."""
        self._u_state = 0.0
        self._v_state = 0.0
        self._w_state = 0.0


@dataclass
class VonKarmanTurbulence:
    """
    Von Karman Wind Turbulence Model.

    Reference:
        Von Karman, T. (1948). "Progress in Statistical Theory of Turbulence"
        Proc. National Academy of Sciences, Vol. 34, No. 11

        MIL-HDBK-1797 Section 3.7.11.2

    The Von Karman model provides more accurate spectral representation
    than Dryden, particularly at high frequencies.

    Power Spectral Density:
        Φ_u(ω) = σ_u² × (2L_u/V) × 1/(1 + (1.339×L_u×ω/V)²)^(5/6)

    Note:
        Von Karman uses fractional-order filters which require
        approximation in time domain.
    """

    altitude_m: float = 100.0
    airspeed_m_s: float = 20.0
    turbulence_intensity: str = "moderate"
    rng: Optional[Any] = None  # Optional RNG for deterministic behavior

    # Filter states (10th order approximation)
    _filter_states: list = field(default_factory=lambda: [0.0] * 10, repr=False)

    def __post_init__(self) -> None:
        self._dryden = DrydenTurbulence(
            altitude_m=self.altitude_m,
            airspeed_m_s=self.airspeed_m_s,
            turbulence_intensity=self.turbulence_intensity,
            rng=self.rng,
        )

    def sample(self, dt: float) -> Tuple[float, float, float]:
        """
        Sample Von Karman turbulence.

        Uses Dryden as approximation with spectral correction.

        Args:
            dt: Time step (s)

        Returns:
            (u, v, w) turbulence velocities (m/s)
        """
        # Use Dryden as base with slight modification for Von Karman spectrum
        u, v, w = self._dryden.sample(dt)

        # Von Karman correction factor (simplified)
        # True Von Karman has (5/6) power law vs Dryden's (1/2)
        correction = 1.05  # Approximate amplitude correction

        return (u * correction, v * correction, w * correction)

    def reset(self) -> None:
        """Reset filter states."""
        self._dryden.reset()
        self._filter_states = [0.0] * 10
