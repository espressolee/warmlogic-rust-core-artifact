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
[Phase 140] 3D Occupancy Mapper.
Maintains a 3D voxel grid representation of the environment.
"""

import math
from typing import Tuple

import numpy as np


class OccupancyMapper:
    """
    3D Occupancy Grid Mapper.
    Projects depth frames into a persistent world map.
    """

    def __init__(self, size_m: float = 100.0, resolution_m: float = 1.0):
        self.size_m = size_m
        self.resolution = resolution_m
        self.dim = int(size_m / resolution_m)

        # Origin is the center of the grid [N, E, D]
        # Using float16/uint8 to save memory if needed, but float32 is fine for 'lite'
        self.grid = np.zeros((self.dim, self.dim, self.dim), dtype=np.float32)

        # Binary grid for occupancy
        self.occupancy = np.zeros((self.dim, self.dim, self.dim), dtype=bool)

    def update(
        self,
        depth_map: np.ndarray,
        pos_ned: np.ndarray,
        attitude_euler_deg: np.ndarray,
        fov_deg: float = 90.0,
    ):
        """
        Updates the occupancy grid with a new depth frame.
        """
        h, w = depth_map.shape
        fov_rad = math.radians(fov_deg)
        f = (w / 2.0) / math.tan(fov_rad / 2.0)

        # Convert Euler to Rotation Matrix (Body to NED)
        R = self._euler_to_rotation_matrix(attitude_euler_deg)

        # Sampling: Dynamic step based on frame size
        step = max(1, w // 16)
        for v in range(0, h, step):
            for u in range(0, w, step):
                depth = depth_map[v, u]
                if depth >= 1000.0 or depth <= 0.1:
                    continue

                # 1. Back-project to Body Frame
                dx = u - w / 2.0
                dy = v - h / 2.0

                # Ray direction in body frame (normalized then scaled by depth)
                ray_body = np.array([f, dx, dy])
                ray_body = ray_body / np.linalg.norm(ray_body) * depth

                # 2. Transform to NED World Frame
                point_ned = pos_ned + (R @ ray_body)

                # 3. Map to Grid Indices
                ix, iy, iz = self._ned_to_grid(point_ned)

                if 0 <= ix < self.dim and 0 <= iy < self.dim and 0 <= iz < self.dim:
                    # Update occupancy (simplistic: overwrite or accumulate)
                    self.grid[ix, iy, iz] += 1.0
                    if self.grid[ix, iy, iz] > 2.0:  # Small threshold
                        self.occupancy[ix, iy, iz] = True

    def _ned_to_grid(self, point_ned: np.ndarray) -> Tuple[int, int, int]:
        """Converts NED coordinates to grid indices."""
        # Offset by center to handle negative NED
        offset = self.size_m / 2.0
        ix = int((point_ned[0] + offset) / self.resolution)
        iy = int((point_ned[1] + offset) / self.resolution)
        iz = int((point_ned[2] + offset) / self.resolution)
        return ix, iy, iz

    def _euler_to_rotation_matrix(self, euler_deg: np.ndarray) -> np.ndarray:
        r, p, y = np.radians(euler_deg)
        R_x = np.array(
            [[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]]
        )
        R_y = np.array(
            [[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]]
        )
        R_z = np.array(
            [[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]]
        )
        return R_z @ R_y @ R_x

    def is_occupied(self, point_ned: np.ndarray) -> bool:
        ix, iy, iz = self._ned_to_grid(point_ned)
        if 0 <= ix < self.dim and 0 <= iy < self.dim and 0 <= iz < self.dim:
            return self.occupancy[ix, iy, iz]
        return False

    def check_collision(
        self,
        start_ned: np.ndarray,
        vel_ned: np.ndarray,
        horizon_s: float = 2.0,
        dt: float = 0.1,
    ) -> Tuple[bool, np.ndarray]:
        """
        Checks if the projected trajectory collides with any occupied voxel.
        Returns (True, collision_point_ned) if collision detected.
        """
        t = dt
        while t <= horizon_s:
            point = start_ned + vel_ned * t
            if self.is_occupied(point):
                return True, point
            t += dt
        return False, np.zeros(3)
