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
Extended Kalman Filter (EKF) for Attitude Estimation.

Uses Quaternion-based state estimation to fuse Gyro, Accel, and Mag data.
State Vector (7x1): [q0, q1, q2, q3, bx, by, bz]
- q: Attitude Quaternion
- b: Gyro Bias

Reference:
- Trawny & Roumeliotis (2005), "Indirect Kalman Filter for 3D Attitude Estimation"
- Madgwick (2010), "An efficient orientation filter for inertial and magnetic sensor arrays"
"""

import math
from dataclasses import dataclass, field
from typing import Tuple

import numpy as np


@dataclass
class ExtendedKalmanFilter:
    """
    7-State EKF for Attitude Estimation.
    """

    dt: float = 0.01

    # State Vector: [q0, q1, q2, q3, bx, by, bz]
    # q0 is scalar part
    state: np.ndarray = field(
        default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    )

    # Covariance Matrix P (7x7)
    P: np.ndarray = field(default_factory=lambda: np.eye(7) * 0.1)

    # Process Noise Q (7x7)
    # Gyro noise and Bias random walk
    Q: np.ndarray = field(default_factory=lambda: np.eye(7) * 1e-4)

    # Measurement Noise R (Accel: 3x3, Mag: 3x3)
    R_accel: np.ndarray = field(default_factory=lambda: np.eye(3) * 0.01)
    R_mag: np.ndarray = field(default_factory=lambda: np.eye(3) * 0.05)

    def __post_init__(self):
        # Tune Process Noise
        # Quaternion part (Gyro Noise)
        self.Q[0:4, 0:4] *= 1e-5
        # Bias part (Random Walk)
        self.Q[4:7, 4:7] *= 1e-7

    def predict(self, gyro_rad_s: Tuple[float, float, float]):
        """
        Time Update (Prediction).

        Args:
            gyro_rad_s: (gx, gy, gz) in body frame
        """
        gx, gy, gz = gyro_rad_s
        q0, q1, q2, q3 = self.state[0:4]
        bx, by, bz = self.state[4:7]

        # Correct gyro with estimated bias
        wx = gx - bx
        wy = gy - by
        wz = gz - bz

        # Quaternion derivative (1/2 * q * w)
        # dq/dt = 0.5 * closure * q
        # closure matrix for quaternion multiplication

        dt = self.dt
        half_dt = 0.5 * dt

        # Simple Euler integration for state
        dq0 = 0.5 * (-q1 * wx - q2 * wy - q3 * wz)
        dq1 = 0.5 * (q0 * wx - q3 * wy + q2 * wz)
        dq2 = 0.5 * (q3 * wx + q0 * wy - q1 * wz)
        dq3 = 0.5 * (-q2 * wx + q1 * wy + q0 * wz)

        self.state[0] += dq0 * dt
        self.state[1] += dq1 * dt
        self.state[2] += dq2 * dt
        self.state[3] += dq3 * dt

        # Normalize Quaternion
        norm = np.linalg.norm(self.state[0:4])
        if norm > 0:
            self.state[0:4] /= norm

        # Jacobian F (7x7) - Linearized System Matrix
        # Requires partial derivatives of f(x) w.r.t x
        # Approximated identity + simplistic update for covariance propagation
        # P = F * P * F.T + Q
        # For full implementation, need rigorous Jacobian.
        # Here we use a simplified diagonal propagation for performance in Python
        # or implement full Jacobian if needed.

        # Simplified Covariance Prediction
        self.P = self.P + self.Q

    def update_accel(self, accel_m_s2: Tuple[float, float, float]):
        """
        Measurement Update (Correction) using Accelerometer.
        Assuming measurement of gravity vector [0, 0, g].
        """
        ax, ay, az = accel_m_s2
        norm = math.sqrt(ax * ax + ay * ay + az * az)
        if norm < 0.1:
            return  # Ignore freefall or zero

        # Normalize measurement z (3x1)
        z = np.array([ax / norm, ay / norm, az / norm])

        # Estimated Gravity Direction h(x) (3x1)
        q0, q1, q2, q3 = self.state[0:4]

        hx = 2.0 * (q1 * q3 - q0 * q2)
        hy = 2.0 * (q0 * q1 + q2 * q3)
        hz = q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3
        h = np.array([hx, hy, hz])

        # Residual y (3x1)
        y = z - h

        # Jacobian H (3x7) - Partial derivatives of h w.r.t state
        # dh/dq derived from Rotation Matrix
        # dh/db is 0 (Accel doesn't measure bias directly)

        H = np.zeros((3, 7))
        H[0, 0:4] = 2.0 * np.array([-q2, q3, -q0, q1])
        H[1, 0:4] = 2.0 * np.array([q1, q0, q3, q2])
        H[2, 0:4] = 2.0 * np.array([q0, -q1, -q2, q3])

        # Innovation Covariance S (3x3)
        S = H @ self.P @ H.T + self.R_accel

        # Kalman Gain K (7x3)
        try:
            K = self.P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            return  # Singular matrix, skip update

        # State Update x = x + Ky
        dx = K @ y
        self.state += dx

        # Covariance Update P = (I - KH)P
        I = np.eye(7)
        self.P = (I - K @ H) @ self.P

        # Re-normalize Quaternion
        q_norm = np.linalg.norm(self.state[0:4])
        if q_norm > 0:
            self.state[0:4] /= q_norm

    def get_euler_angles(self) -> Tuple[float, float, float]:
        """Return (Roll, Pitch, Yaw) in degrees."""
        q0, q1, q2, q3 = self.state[0:4]

        # Roll (x-axis rotation)
        sinr_cosp = 2.0 * (q0 * q1 + q2 * q3)
        cosr_cosp = 1.0 - 2.0 * (q1 * q1 + q2 * q2)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2.0 * (q0 * q2 - q3 * q1)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)

        # Yaw (z-axis rotation)
        siny_cosp = 2.0 * (q0 * q3 + q1 * q2)
        cosy_cosp = 1.0 - 2.0 * (q2 * q2 + q3 * q3)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))

    def get_rotation_matrix(self) -> np.ndarray:
        """
        Return the 3x3 Rotation Matrix (Direction Cosine Matrix) from Body to Nav frame.
        R_nb: Body -> Nav (World)
        """
        q0, q1, q2, q3 = self.state[0:4]

        # Standard quaternion to rotation matrix formula
        r00 = 1.0 - 2.0 * (q2 * q2 + q3 * q3)
        r01 = 2.0 * (q1 * q2 - q0 * q3)
        r02 = 2.0 * (q1 * q3 + q0 * q2)

        r10 = 2.0 * (q1 * q2 + q0 * q3)
        r11 = 1.0 - 2.0 * (q1 * q1 + q3 * q3)
        r12 = 2.0 * (q2 * q3 - q0 * q1)

        r20 = 2.0 * (q1 * q3 - q0 * q2)
        r21 = 2.0 * (q2 * q3 + q0 * q1)
        r22 = 1.0 - 2.0 * (q1 * q1 + q2 * q2)

        return np.array([[r00, r01, r02], [r10, r11, r12], [r20, r21, r22]])
