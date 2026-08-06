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
[Phase 140] Visual Inertial Odometry (VIO).
Estimates drone motion by tracking depth changes across successive frames.
"""

from typing import Optional

import numpy as np


class VisualOdometry:
    """
    Lightweight Visual Odometry.
    Uses depth maps to estimate relative motion (velocity).
    """

    def __init__(self, fov_deg: float = 90.0, width: int = 64, height: int = 48):
        self.fov_rad = np.radians(fov_deg)
        self.width = width
        self.height = height
        self.focal_length = (width / 2.0) / np.tan(self.fov_rad / 2.0)

        self.prev_depth_map: Optional[np.ndarray] = None
        self.prev_pos_est: np.ndarray = np.zeros(3)  # [N, E, D]
        self.vel_est: np.ndarray = np.zeros(3)  # [m/s]

    def update(self, depth_map: np.ndarray, dt: float) -> np.ndarray:
        """
        Estimates velocity by comparing current depth map with the previous one.
        Simplified 'Depth Flow' algorithm.
        """
        if self.prev_depth_map is None:
            self.prev_depth_map = depth_map.copy()
            return self.vel_est

        # Calculate 'Optical Flow' on the depth map
        # For simplicity in this 'lite' implementation, we'll use the change in
        # average depth of central pixels to estimate forward/backward motion
        # and shifts to estimate lateral motion.

        # 1. Forward/Backward (X/North in Body)
        # Average depth change in the center 10x10 area
        h, w = depth_map.shape
        cy, cx = h // 2, w // 2
        center_curr = depth_map[cy - 5 : cy + 5, cx - 5 : cx + 5]
        center_prev = self.prev_depth_map[cy - 5 : cy + 5, cx - 5 : cx + 5]

        # d_prev = d_curr + v*dt (roughly)
        delta_d = np.mean(center_prev) - np.mean(center_curr)
        v_x_body = delta_d / dt if dt > 0 else 0.0

        # 2. Lateral shifts (Y/East and Z/Down)
        # We can use cross-correlation or simple differencing to find best shift
        # For 'lite' version, we'll implement a primitive shift search
        # (This is a placeholder for a more complex LK-tracker)
        # v_y_body = 0.0 # Removed as per instruction
        # v_z_body = 0.0 # Removed as per instruction

        # Fuse with existing estimates or use as direct measurement
        # Filter the noisy estimate
        alpha = 0.2
        self.vel_est[0] = (1 - alpha) * self.vel_est[0] + alpha * v_x_body

        self.prev_depth_map = depth_map.copy()
        return self.vel_est

    def set_initial_pose(self, pos_ned: np.ndarray):
        self.prev_pos_est = pos_ned.copy()
