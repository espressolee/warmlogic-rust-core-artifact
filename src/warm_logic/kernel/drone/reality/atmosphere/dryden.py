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
import math
import random
from typing import Optional, Tuple


class LowPassFilter:
    """Simple LPF for shaping white noise into colored noise."""

    def __init__(self, cutoff_freq_hz: float, dt: float):
        self.cutoff_freq_hz = cutoff_freq_hz
        self.dt = dt
        rc = 1.0 / (2.0 * math.pi * cutoff_freq_hz)
        self.alpha = dt / (rc + dt)
        self.output = 0.0

    def update(self, input_val: float) -> float:
        self.output = self.output + self.alpha * (input_val - self.output)
        return self.output


class DrydenGustModel:
    """
    Dryden Wind Turbulence Model based on MIL-F-8785C.
    Generates spatially correlated wind gusts (u_g, v_g, w_g).
    """

    def __init__(self, dt: float = 0.01):
        self.dt = dt

        # Internal state for shaping filters
        # u, v, w components require separate filters
        self._filter_u: Optional[LowPassFilter] = None
        self._filter_v: Optional[LowPassFilter] = None
        self._filter_w: Optional[LowPassFilter] = None

        # Current gust values
        self.gust_u = 0.0
        self.gust_v = 0.0
        self.gust_w = 0.0

    def get_turbulence(
        self, altitude_m: float, airspeed_m_s: float
    ) -> Tuple[float, float, float]:
        """
        Calculate turbulence components (u_g, v_g, w_g) for current flight condition.

        Args:
            altitude_m: Flight altitude in meters.
            airspeed_m_s: Flight speed in m/s (Va).

        Returns:
            Tuple (u_g, v_g, w_g) in body frame (ft/s converted to m/s).
        """
        h = max(0.1, min(altitude_m * 3.28084, 10000.0))  # Convert to feet, clamp
        V = max(1.0, airspeed_m_s * 3.28084)  # Convert to ft/s, clamp min

        # MIL-F-8785C Parameters for Low Altitude (< 1000 ft)
        # Sigma (Turbulence Intensity)
        # Sigma (Turbulence Intensity)
        # W_20 = 15.0 * 1.68781  # 15 knots at 20ft (Moderate turbulence) -> Too strong for initial tuning
        W_20 = 5.0 * 1.68781  # 5 knots (Light turbulence)
        sigma_w = 0.1 * W_20
        sigma_u = sigma_w / ((0.177 + 0.000823 * h) ** 0.4)
        sigma_v = sigma_u

        # Length Scales (L)
        L_w = h
        L_u = h / ((0.177 + 0.000823 * h) ** 1.2)
        L_v = L_u

        # Time Constraints (V/L)
        # We model this using LPF with noise input
        # Transfer function H(s) ~ sigma * sqrt(2L/V) / (1 + (L/V)s)

        # Compute cutoff frequencies for shaping filters (rad/s -> Hz)
        # omega = V / L
        omega_u = V / L_u
        omega_v = V / L_v
        omega_w = V / L_w

        # Initialize filters on first run
        if self._filter_u is None:
            self._filter_u = LowPassFilter(
                cutoff_freq_hz=omega_u / (2 * math.pi), dt=self.dt
            )
            self._filter_v = LowPassFilter(
                cutoff_freq_hz=omega_v / (2 * math.pi), dt=self.dt
            )
            self._filter_w = LowPassFilter(
                cutoff_freq_hz=omega_w / (2 * math.pi), dt=self.dt
            )

        # Local refs for type narrowing
        filter_u = self._filter_u
        filter_v = self._filter_v
        filter_w = self._filter_w
        if filter_v is None or filter_w is None:
            raise RuntimeError("Dryden filters not initialized - call configure() first")

        # Update filter cutoffs (dynamic based on speed/alt)
        filter_u.cutoff_freq_hz = omega_u / (2 * math.pi)
        filter_v.cutoff_freq_hz = omega_v / (2 * math.pi)
        filter_w.cutoff_freq_hz = omega_w / (2 * math.pi)

        # Generate White Noise
        # For discrete integration, white noise variance needs to be scaled by 1/dt
        # to maintain PSD magnitude.
        # However, since we simply drive the LPF with random values:
        # The variance of the output of an LPF driven by white noise N(0, 1) is sigma^2 * alpha / (2).
        # We want output variance to be sigma^2.
        # Let's use the explicit transfer function form:
        # H(s) = sigma * sqrt(2*L/V) / (1 + (L/V)s)
        # This is equivalent to LPF with gain K = sigma * sqrt(2/omega) and cutoff omega.
        # But for digital implementation, it's easier to scale the noise input directly.

        # Scaling factor to achieve unit variance through LPF with cutoff omega:
        # We want output std dev = sigma.
        # Driving LPF with N(0,1) * Scale gives output variance = Scale^2 * alpha / (2-alpha).
        # So Scale = sigma * sqrt((2-alpha)/alpha).

        # Calculate alphas for current cutoffs
        alpha_u = filter_u.alpha
        alpha_v = filter_v.alpha
        alpha_w = filter_w.alpha

        gain_u = sigma_u * math.sqrt((2 - alpha_u) / alpha_u)
        gain_v = sigma_v * math.sqrt((2 - alpha_v) / alpha_v)
        gain_w = sigma_w * math.sqrt((2 - alpha_w) / alpha_w)

        noise_u = random.gauss(0, 1) * gain_u
        noise_v = random.gauss(0, 1) * gain_v
        noise_w = random.gauss(0, 1) * gain_w

        # Apply Filters
        ug_ft = filter_u.update(noise_u)
        vg_ft = filter_v.update(noise_v)
        wg_ft = filter_w.update(noise_w)

        # Convert back to m/s
        return (ug_ft * 0.3048, vg_ft * 0.3048, wg_ft * 0.3048)
