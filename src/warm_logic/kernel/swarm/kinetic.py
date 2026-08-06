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
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

logger = logging.getLogger("KineticSwarm")


@dataclass
class SwarmPeerState:
    node_id: str
    position_ned: np.ndarray  # [N, E, D] in meters
    velocity_ned: np.ndarray  # [VN, VE, VD] in m/s
    last_update: float = field(default_factory=time.time)


class KineticSwarmEngine:
    """
    [Phase 160] Kinetic Swarm Engine.
    Handles multi-drone coordination using Boids-inspired behavioral rules
    and structured geometric formations.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.peers: Dict[str, SwarmPeerState] = {}

        # Boids Weights
        self.weight_separation = 1.5
        self.weight_alignment = 1.0
        self.weight_cohesion = 1.0

        # Boids Radii
        self.radius_separation = 5.0  # Meters: Keep away!
        self.radius_alignment = 20.0  # Meters: Match speed within this range
        self.radius_cohesion = 30.0  # Meters: Stay close to the group

        # Formation Settings
        self.formation_active = False
        self.formation_type = "V-SHAPE"  # V-SHAPE, GRID, CIRCLE
        self.formation_spacing = 10.0
        self.formation_index = 0  # Our position in the formation

    def update_peer(
        self,
        node_id: str,
        pos: Tuple[float, float, float],
        vel: Tuple[float, float, float],
    ):
        """Updates or adds a peer state."""
        if node_id == self.node_id:
            return

        self.peers[node_id] = SwarmPeerState(
            node_id=node_id,
            position_ned=np.array(pos),
            velocity_ned=np.array(vel),
            last_update=time.time(),
        )

        # Cleanup stale peers (> 2 seconds)
        now = time.time()
        stale = [nid for nid, p in self.peers.items() if now - p.last_update > 2.0]
        for nid in stale:
            del self.peers[nid]

    def calculate_swarm_force(
        self, my_pos: np.ndarray, my_vel: np.ndarray
    ) -> np.ndarray:
        """
        Calculates the combined behavioral force (acceleration vector).
        """
        if not self.peers:
            return np.zeros(3)

        force_sep = self._calculate_separation(my_pos)
        force_ali = self._calculate_alignment(my_vel)
        force_coh = self._calculate_cohesion(my_pos)

        total_force = (
            self.weight_separation * force_sep
            + self.weight_alignment * force_ali
            + self.weight_cohesion * force_coh
        )

        return total_force

    def _calculate_separation(self, my_pos: np.ndarray) -> np.ndarray:
        force = np.zeros(3)
        count = 0
        for peer in self.peers.values():
            diff = my_pos - peer.position_ned
            dist = np.linalg.norm(diff)
            if 0 < dist < self.radius_separation:
                # Force is inversely proportional to distance
                force += diff / (dist**2)
                count += 1
        return force / count if count > 0 else force

    def _calculate_alignment(self, my_vel: np.ndarray) -> np.ndarray:
        avg_vel = np.zeros(3)
        count = 0
        for peer in self.peers.values():
            avg_vel += peer.velocity_ned
            count += 1

        if count > 0:
            avg_vel /= count
            return avg_vel - my_vel
        return avg_vel

    def _calculate_cohesion(self, my_pos: np.ndarray) -> np.ndarray:
        center_of_mass = np.zeros(3)
        count = 0
        for peer in self.peers.values():
            center_of_mass += peer.position_ned
            count += 1

        if count > 0:
            center_of_mass /= count
            return center_of_mass - my_pos
        return center_of_mass

    def get_formation_offset(self) -> np.ndarray:
        """
        Returns the NED offset from formation center for this node.
        """
        if not self.formation_active:
            return np.zeros(3)

        idx = self.formation_index
        s = self.formation_spacing

        if self.formation_type == "V-SHAPE":
            # Node 0 at tip [0,0,0]
            # Node 1 at [-s, s, 0], Node 2 at [-s, -s, 0]
            # Node 3 at [-2s, 2s, 0], Node 4 at [-2s, -2s, 0]
            row = (idx + 1) // 2
            side = 1 if idx % 2 != 0 else -1
            if idx == 0:
                return np.zeros(3)
            return np.array([-row * s, side * row * s, 0.0])

        elif self.formation_type == "GRID":
            cols = 3
            r = idx // cols
            c = idx % cols
            return np.array([-r * s, c * s, 0.0])

        return np.zeros(3)
