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
[Phase 140] Synthetic Vision Simulator (Eagle Eye).
Simulates a pinhole camera to generate depth and edge maps.
"""

import math
from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class Obstacle:
    """Simple 3D obstacle in the world (NED)."""

    name: str
    pos_ned: np.ndarray  # [N, E, D]
    radius: float


class VisionSimulator:
    """
    Synthetic Camera Simulator.
    Generates depth maps based on drone position and world geometry.
    """

    def __init__(self, width: int = 64, height: int = 48, fov_deg: float = 90.0):
        self.width = width
        self.height = height
        self.fov_rad = math.radians(fov_deg)

        # Precompute ray directions in body frame (assuming camera points forward)
        # Forward is X (North), Right is Y (East), Down is Z
        self._init_rays()

        # World objects for the "Eagle Eye" to see
        self.obstacles: List[Obstacle] = [
            Obstacle("TallTower", np.array([50.0, 50.0, -20.0]), 5.0),
            Obstacle("Warehouse", np.array([100.0, -30.0, -10.0]), 10.0),
            Obstacle("TreeCluster", np.array([-20.0, 80.0, -5.0]), 3.0),
        ]

    def _init_rays(self):
        """Precompute unit vectors for each pixel in camera frame."""
        # Focal length in pixels
        f = (self.width / 2.0) / math.tan(self.fov_rad / 2.0)

        self.ray_directions = np.zeros((self.height, self.width, 3))
        for v in range(self.height):
            for u in range(self.width):
                # Pixel center relative to image center
                dx = u - self.width / 2.0
                dy = v - self.height / 2.0

                # In camera frame: X=Forward, Y=Right, Z=Down
                # Ray vector: [f, dx, dy] normalized
                ray = np.array([f, dx, dy])
                self.ray_directions[v, u] = ray / np.linalg.norm(ray)

    def render_depth(
        self, pos_ned: np.ndarray, attitude_euler_deg: np.ndarray
    ) -> np.ndarray:
        """
        Renders a depth map from the current drone pose.
        Args:
            pos_ned: Current position [N, E, D]
            attitude_euler_deg: [roll, pitch, yaw] in degrees
        Returns:
            height x width numpy array of depth values.
        """
        # Convert Euler to Rotation Matrix (Body to NED)
        R = self._euler_to_rotation_matrix(attitude_euler_deg)

        depth_map = np.full((self.height, self.width), 1000.0)  # Far plane

        # For each pixel, find intersection with ground (D=0) and obstacles
        for v in range(self.height):
            for u in range(self.width):
                # Ray direction in NED frame
                body_ray = self.ray_directions[v, u]
                ned_ray = R @ body_ray

                # 1. Intersection with Ground (D = 0)
                # pos_ned[2] + t * ned_ray[2] = 0  => t = -pos_ned[2] / ned_ray[2]
                if ned_ray[2] > 1e-6:  # Ray pointing down
                    t_ground = -pos_ned[2] / ned_ray[2]
                    if t_ground > 0:
                        depth_map[v, u] = t_ground

                # 2. Intersection with Obstacles (Spheres for now)
                for obs in self.obstacles:
                    t_obs = self._ray_sphere_intersect(
                        pos_ned, ned_ray, obs.pos_ned, obs.radius
                    )
                    if t_obs is not None and t_obs > 0:
                        depth_map[v, u] = min(depth_map[v, u], t_obs)

        return depth_map

    def _euler_to_rotation_matrix(self, euler_deg: np.ndarray) -> np.ndarray:
        """Standard ZYX rotation matrix (Yaw-Pitch-Roll)."""
        r, p, y = np.radians(euler_deg)

        # Rotation matrices for each axis
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

    def _ray_sphere_intersect(self, r_o, r_d, s_o, s_r) -> Optional[float]:
        """Ray-Sphere intersection test."""
        oc = r_o - s_o
        a = np.dot(r_d, r_d)
        b = 2.0 * np.dot(oc, r_d)
        c = np.dot(oc, oc) - s_r * s_r
        discriminant = b * b - 4 * a * c

        if discriminant < 0:
            return None
        else:
            return (-b - math.sqrt(discriminant)) / (2.0 * a)
