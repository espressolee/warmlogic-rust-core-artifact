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
[Phase 201] Minimum-Jerk Trajectory Generator.
Implements Quintic Splines (5th-order polynomials) for smooth waypoint transitions.
"""

from typing import Dict, Tuple

import numpy as np


class QuinticSpline:
    """
    Polynomial: p(t) = a0 + a1*t + a2*t^2 + a3*t^3 + a4*t^4 + a5*t^5
    Designed to minimize the integral of squared jerk.
    """

    def __init__(
        self,
        start_pos: float,
        start_vel: float,
        start_acc: float,
        end_pos: float,
        end_vel: float,
        end_acc: float,
        duration: float,
    ):
        self.T = duration
        if self.T <= 0:
            self.coeffs = np.array([start_pos, 0, 0, 0, 0, 0])
            return

        # Solve for coefficients [a0, a1, a2, a3, a4, a5]
        # a0 = p0
        # a1 = v0
        # a2 = a0 / 2
        a0 = start_pos
        a1 = start_vel
        a2 = start_acc / 2.0

        # Matrix for [a3, a4, a5]
        # T^3 a3 + T^4 a4 + T^5 a5 = pT - p0 - v0T - 0.5 a0 T^2
        # 3T^2 a3 + 4T^3 a4 + 5T^4 a5 = vT - v0 - a0 T
        # 6T a3 + 12T^2 a4 + 20T^3 a5 = aT - a0
        A = np.array(
            [
                [self.T**3, self.T**4, self.T**5],
                [3 * self.T**2, 4 * self.T**3, 5 * self.T**4],
                [6 * self.T, 12 * self.T**2, 20 * self.T**3],
            ]
        )

        b = np.array(
            [
                end_pos - start_pos - start_vel * self.T - 0.5 * start_acc * self.T**2,
                end_vel - start_vel - start_acc * self.T,
                end_acc - start_acc,
            ]
        )

        try:
            x = np.linalg.solve(A, b)
            self.coeffs = np.array([a0, a1, a2, x[0], x[1], x[2]])
        except np.linalg.LinAlgError:
            self.coeffs = np.array([start_pos, 0, 0, 0, 0, 0])

    def sample(self, t: float) -> Tuple[float, float, float]:
        """Returns (pos, vel, acc) at time t."""
        if t <= 0:
            return self.coeffs[0], self.coeffs[1], self.coeffs[2] * 2.0
        if t >= self.T:
            # Recompute end state to avoid precision drift
            t = self.T

        p = np.polyval(self.coeffs[::-1], t)
        v_coeffs = np.array(
            [
                5 * self.coeffs[5],
                4 * self.coeffs[4],
                3 * self.coeffs[3],
                2 * self.coeffs[2],
                self.coeffs[1],
            ]
        )
        v = np.polyval(v_coeffs, t)

        a_coeffs = np.array(
            [
                20 * self.coeffs[5],
                12 * self.coeffs[4],
                6 * self.coeffs[3],
                2 * self.coeffs[2],
            ]
        )
        a = np.polyval(a_coeffs, t)

        return p, v, a


class TrajectoryGenerator:
    """
    Manages 3D quintic splines for smooth multi-waypoint navigation.
    """

    def __init__(self, mass: float = 2.5):
        self.mass = mass
        self.splines: Dict[str, QuinticSpline] = {}
        self.start_time: float = 0.0
        self.duration: float = 0.0
        self.active: bool = False

    def generate(
        self,
        current_pos: np.ndarray,
        current_vel: np.ndarray,
        current_accel: np.ndarray,
        target_pos: np.ndarray,
        target_vel: np.ndarray = np.zeros(3),
        target_acc: np.ndarray = np.zeros(3),
        duration: float = 5.0,
        start_time: float = 0.0,
    ):
        """
        Generates 3 independent splines for NED coordinates.
        """
        self.start_time = start_time
        self.duration = duration
        self.active = True

        self.splines = {
            "n": QuinticSpline(
                current_pos[0],
                current_vel[0],
                current_accel[0],
                target_pos[0],
                target_vel[0],
                target_acc[0],
                duration,
            ),
            "e": QuinticSpline(
                current_pos[1],
                current_vel[1],
                current_accel[1],
                target_pos[1],
                target_vel[1],
                target_acc[1],
                duration,
            ),
            "d": QuinticSpline(
                current_pos[2],
                current_vel[2],
                current_accel[2],
                target_pos[2],
                target_vel[2],
                target_acc[2],
                duration,
            ),
        }

    def sample(self, current_time: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Returns smooth (Pos, Vel, Acc) setpoints for the controller.
        """
        if not self.active:
            return None, None, None

        t = current_time - self.start_time
        if t >= self.duration:
            t = self.duration
            # Keep active until explicitly cleared or target changed

        pn, vn, an = self.splines["n"].sample(t)
        pe, ve, ae = self.splines["e"].sample(t)
        pd, vd, ad = self.splines["d"].sample(t)

        return (
            np.array([pn, pe, pd]),
            np.array([vn, ve, vd]),
            np.array([an, ae, ad]),
        )
