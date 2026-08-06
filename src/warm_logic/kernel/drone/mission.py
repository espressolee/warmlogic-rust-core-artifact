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
[Phase 115.4] Mission Planning.
Route optimization and waypoint management.
Target: < 100ms replanning.
"""

import heapq
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .types import GeoFence, Position, Waypoint

logger = logging.getLogger("DroneMission")


@dataclass
class MissionPlan:
    """A complete mission plan."""

    id: str
    name: str
    waypoints: List[Waypoint]
    total_distance: float  # meters
    estimated_time: float  # seconds
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "waypoints": [w.to_dict() for w in self.waypoints],
            "total_distance_m": self.total_distance,
            "estimated_time_s": self.estimated_time,
        }


class MissionPlanner:
    """
    [Phase 115.4] Mission Planner.

    Features:
    - Waypoint management
    - A* path planning
    - Obstacle avoidance
    - Dynamic replanning

    Performance: < 100ms replanning
    """

    def __init__(self) -> None:
        self._mission_counter = 0
        self._waypoint_counter = 0
        self._current_mission: Optional[MissionPlan] = None
        self._current_waypoint_idx = 0
        self._obstacles: List[GeoFence] = []

        logger.info("[MissionPlanner] Active.")

    def _gen_mission_id(self) -> str:
        self._mission_counter += 1
        return f"MSN{self._mission_counter:04d}"

    def _gen_waypoint_id(self) -> str:
        self._waypoint_counter += 1
        return f"WP{self._waypoint_counter:04d}"

    def create_mission(
        self, name: str, waypoints: List[Position], speed: float = 10.0
    ) -> MissionPlan:
        """Create a mission from positions."""
        start = time.time()

        wps = []
        total_distance = 0.0

        for i, pos in enumerate(waypoints):
            wp = Waypoint(id=self._gen_waypoint_id(), position=pos, speed=speed)
            wps.append(wp)

            if i > 0:
                total_distance += waypoints[i - 1].distance_to(pos)

        estimated_time = total_distance / speed if speed > 0 else 0

        mission = MissionPlan(
            id=self._gen_mission_id(),
            name=name,
            waypoints=wps,
            total_distance=total_distance,
            estimated_time=estimated_time,
        )

        self._current_mission = mission
        self._current_waypoint_idx = 0

        elapsed = (time.time() - start) * 1000
        logger.info(
            f"Mission '{name}' created: {len(wps)} waypoints, "
            f"{total_distance:.0f}m, {elapsed:.1f}ms"
        )

        return mission

    def plan_route(
        self,
        start: Position,
        goal: Position,
        obstacles: Optional[List[GeoFence]] = None,
    ) -> List[Position]:
        """
        Plan optimal route avoiding obstacles.
        Uses simplified A* algorithm.
        """
        plan_start = time.time()

        obstacles = obstacles or self._obstacles

        # If no obstacles, direct path
        if not obstacles:
            elapsed = (time.time() - plan_start) * 1000
            return [start, goal]

        # Grid-based A* for obstacle avoidance
        path = self._astar(start, goal, obstacles)

        elapsed = (time.time() - plan_start) * 1000
        logger.debug(f"Route planned: {len(path)} points in {elapsed:.1f}ms")

        return path

    def _astar(
        self, start: Position, goal: Position, obstacles: List[GeoFence]
    ) -> List[Position]:
        """A* pathfinding implementation."""
        # Simplified grid-based approach
        # In production, would use proper 3D grid or RRT*

        def heuristic(a: Position, b: Position) -> float:
            return a.distance_to(b)

        def is_blocked(pos: Position) -> bool:
            for obs in obstacles:
                if obs.fence_type == "exclude" and obs.contains(pos):
                    return True
            return False

        # Grid resolution
        step = 100.0  # meters

        # Generate neighbors
        def get_neighbors(pos: Position) -> List[Position]:
            neighbors = []
            for dlat in [-step / 111000, 0, step / 111000]:  # ~111km per degree
                for dlon in [-step / 111000, 0, step / 111000]:
                    if dlat == 0 and dlon == 0:
                        continue
                    new_pos = Position(
                        pos.latitude + dlat, pos.longitude + dlon, pos.altitude
                    )
                    if not is_blocked(new_pos):
                        neighbors.append(new_pos)
            return neighbors

        # A* search
        open_set = [(0, id(start), start)]
        came_from: Dict[str, Position] = {}
        g_score: Dict[str, float] = {self._pos_key(start): 0}

        max_iterations = 1000
        iterations = 0

        while open_set and iterations < max_iterations:
            iterations += 1
            _, _, current = heapq.heappop(open_set)

            if current.distance_to(goal) < step:
                # Reconstruct path
                path = [goal]
                key = self._pos_key(current)
                while key in came_from:
                    path.append(came_from[key])
                    key = self._pos_key(came_from[key])
                path.append(start)
                return list(reversed(path))

            for neighbor in get_neighbors(current):
                tentative_g = g_score.get(
                    self._pos_key(current), float("inf")
                ) + current.distance_to(neighbor)

                n_key = self._pos_key(neighbor)
                if tentative_g < g_score.get(n_key, float("inf")):
                    came_from[n_key] = current
                    g_score[n_key] = tentative_g
                    f_score = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, id(neighbor), neighbor))

        # No path found, return direct path
        return [start, goal]

    def _pos_key(self, pos: Position) -> str:
        """Create hash key for position."""
        return f"{pos.latitude:.6f},{pos.longitude:.6f},{pos.altitude:.1f}"

    def replan(
        self, current_pos: Position, new_obstacles: Optional[List[GeoFence]] = None
    ) -> MissionPlan:
        """
        Replan remaining mission from current position.
        Target: < 100ms
        """
        start = time.time()

        if not self._current_mission:
            raise ValueError("No active mission")

        obstacles = new_obstacles or self._obstacles

        # Get remaining waypoints
        remaining = self._current_mission.waypoints[self._current_waypoint_idx :]

        if not remaining:
            return self._current_mission

        # Replan path to next waypoint
        new_path = self.plan_route(current_pos, remaining[0].position, obstacles)

        # Create intermediate waypoints
        new_waypoints = []
        for pos in new_path[:-1]:  # Exclude last (it's the original waypoint)
            new_waypoints.append(
                Waypoint(
                    id=self._gen_waypoint_id(), position=pos, speed=remaining[0].speed
                )
            )

        # Add remaining original waypoints
        new_waypoints.extend(remaining)

        # Update mission
        total_distance = sum(
            new_waypoints[i].position.distance_to(new_waypoints[i + 1].position)
            for i in range(len(new_waypoints) - 1)
        )

        self._current_mission.waypoints = new_waypoints
        self._current_mission.total_distance = total_distance
        self._current_waypoint_idx = 0

        elapsed = (time.time() - start) * 1000
        logger.info(f"Replanned in {elapsed:.1f}ms: {len(new_waypoints)} waypoints")

        return self._current_mission

    def get_next_waypoint(self) -> Optional[Waypoint]:
        """Get next waypoint in mission."""
        if not self._current_mission:
            return None

        wps = self._current_mission.waypoints
        if self._current_waypoint_idx >= len(wps):
            return None

        return wps[self._current_waypoint_idx]

    def advance_waypoint(self) -> None:
        """Move to next waypoint."""
        self._current_waypoint_idx += 1

    def get_progress(self) -> Dict[str, Any]:
        """Get mission progress."""
        if not self._current_mission:
            return {"active": False}

        total = len(self._current_mission.waypoints)
        current = self._current_waypoint_idx

        return {
            "active": True,
            "mission_id": self._current_mission.id,
            "current_waypoint": current,
            "total_waypoints": total,
            "progress_pct": (current / total * 100) if total > 0 else 0,
            "distance_remaining_m": self._current_mission.total_distance,
        }

    def add_obstacle(self, obstacle: GeoFence) -> None:
        """Add dynamic obstacle."""
        self._obstacles.append(obstacle)
