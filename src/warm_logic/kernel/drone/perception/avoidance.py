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
[Phase 140] Obstacle Avoidance Logic.
Provides safety monitoring and autonomous evasive maneuvers.
"""

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import numpy as np

from .mapper import OccupancyMapper


class SafetyLevel(Enum):
    SAFE = auto()
    WARNING = auto()  # Decrease velocity, prepare to maneuver
    CRITICAL = auto()  # Emergency Stop or Hard Bank


@dataclass
class SafetyStatus:
    level: SafetyLevel
    suggested_velocity: Optional[np.ndarray] = (
        None  # NED or Body? Let's use NED for Controller.
    )
    nearest_obstacle_dist: float = float("inf")


class SafetyMonitor:
    """
    Monitors the flight path for obstacles using the OccupancyMapper.
    Acts as a 'virtual bumper' and 'path clearer'.
    """

    def __init__(self, mapper: OccupancyMapper):
        self.mapper = mapper
        self.lookahead_time_s = 2.0
        self.warning_dist_m = 5.0
        self.critical_dist_m = 2.0

    def check_safety(self, pos_ned: np.ndarray, vel_ned: np.ndarray) -> SafetyStatus:
        """
        Checks the current velocity vector for collisions.
        Returns a safety status and potential avoidance velocity.
        """
        speed = np.linalg.norm(vel_ned)
        if speed < 0.1:
            return SafetyStatus(SafetyLevel.SAFE)

        # 1. Check primary trajectory (Center)
        collision, point = self.mapper.check_collision(
            start_ned=pos_ned, vel_ned=vel_ned, horizon_s=self.lookahead_time_s, dt=0.2
        )

        if not collision:
            return SafetyStatus(SafetyLevel.SAFE)

        # [Phase 161] Filter out ground-plane false positives only when the
        # predicted collision is near ground but meaningfully below the vehicle.
        ground_plane_m = -0.5
        ground_false_positive_margin_m = 2.0
        if (
            point[2] >= ground_plane_m
            and (point[2] - pos_ned[2]) > ground_false_positive_margin_m
        ):
            return SafetyStatus(SafetyLevel.SAFE)

        # Collision detected!
        dist = np.linalg.norm(point - pos_ned)

        if dist < self.critical_dist_m:
            # Emergency stop: obstacle is inside hard safety boundary.
            return SafetyStatus(
                SafetyLevel.CRITICAL,
                suggested_velocity=np.zeros(3),
                nearest_obstacle_dist=dist,
            )

        # Warning / Evasive Maneuver needed
        # Simple "Bypass": Check Left, Right, Up, Down candidates

        # Create candidate velocities by rotating the velocity vector
        # For simplicity, we just try to find *any* clear path in a 45-degree cone
        # or just stop if too close.

        # Try finding a clear path
        best_evasive_vel = self._find_evasive_vector(pos_ned, vel_ned, speed)

        if best_evasive_vel is not None:
            return SafetyStatus(
                SafetyLevel.WARNING,
                suggested_velocity=best_evasive_vel,
                nearest_obstacle_dist=dist,
            )
        else:
            # No clear path found -> Stop
            return SafetyStatus(
                SafetyLevel.CRITICAL,
                suggested_velocity=np.zeros(3),
                nearest_obstacle_dist=dist,
            )

    def _find_evasive_vector(
        self, pos: np.ndarray, vel: np.ndarray, speed: float
    ) -> Optional[np.ndarray]:
        """Tries to find a collision-free vector by perturbing the current velocity."""
        # Normalize velocity
        v_unit = vel / speed

        # Try rotating around Z (Yaw) +/- 30, 60 degrees
        # Try pitching up/down +/- 30 degrees

        # Simple set of candidates: [Left, Right, Up, Down] (Body relative approx)
        # Actually easier to just generate a few random or fixed perturbations in NED

        candidates = []

        # Side deviations (assuming velocity is roughly horizontal, we rotate around Down)
        # Check Right (+30 deg yaw)
        candidates.append(self._rotate_vector_z(v_unit, 30))
        # Check Left (-30 deg yaw)
        candidates.append(self._rotate_vector_z(v_unit, -30))
        # Check Up (add vertical component)
        up_vec = v_unit.copy()
        up_vec[2] -= 0.5  # Climb (NED Up is negative Z)
        candidates.append(up_vec / np.linalg.norm(up_vec))

        for cand in candidates:
            # Check this new path
            coll, _ = self.mapper.check_collision(
                pos, cand * speed, self.lookahead_time_s, 0.2
            )
            if not coll:
                return cand * speed  # Return scaled velocity

        return None

    def _rotate_vector_z(self, v: np.ndarray, deg: float) -> np.ndarray:
        rad = math.radians(deg)
        c, s = math.cos(rad), math.sin(rad)
        x, y, z = v
        new_x = x * c - y * s
        new_y = x * s + y * c
        return np.array([new_x, new_y, z])
