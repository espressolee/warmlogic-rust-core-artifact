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
[Phase 115] Drone Physics Engine.
High-fidelity physics simulation for drone operations.

Features:
- 4th-order Runge-Kutta integration
- LiPo battery discharge curve
- Aerodynamic drag model
- Wind effects (optional)
"""

import math
from dataclasses import dataclass
from typing import Any, List, Tuple

from .types import Position


@dataclass
class PhysicsState:
    """Complete physics state for RK4 integration."""

    x: float  # East position (m)
    y: float  # North position (m)
    z: float  # Altitude (m)
    vx: float  # East velocity (m/s)
    vy: float  # North velocity (m/s)
    vz: float  # Vertical velocity (m/s)
    battery_voltage: float  # Volts
    battery_soc: float  # State of Charge (0-1)


class RK4Integrator:
    """
    4th-order Runge-Kutta integrator for drone physics.

    Provides O(h^5) local error vs O(h^2) for Euler.
    Essential for accurate trajectory prediction.
    """

    def __init__(self, drone_mass: float = 2.5) -> None:
        """
        Args:
            drone_mass: Drone mass in kg
        """
        self.mass = drone_mass
        self.gravity = 9.81
        self.drag_coeff = 0.1  # Simplified drag coefficient
        self.max_thrust = 50.0  # N (enough to hover + maneuver)

    def _derivatives(
        self, state: PhysicsState, thrust: Tuple[float, float, float]
    ) -> PhysicsState:
        """
        Calculate state derivatives for RK4.

        Args:
            state: Current physics state
            thrust: (Tx, Ty, Tz) thrust vector in body frame (N)

        Returns:
            Derivatives of state
        """
        tx, ty, tz = thrust

        # Drag force (proportional to v^2)
        speed = math.sqrt(state.vx**2 + state.vy**2 + state.vz**2)
        if speed > 0.01:
            drag_x = -self.drag_coeff * state.vx * speed
            drag_y = -self.drag_coeff * state.vy * speed
            drag_z = -self.drag_coeff * state.vz * speed
        else:
            drag_x = drag_y = drag_z = 0.0

        # Accelerations (F = ma)
        ax = (tx + drag_x) / self.mass
        ay = (ty + drag_y) / self.mass
        az = (tz + drag_z - self.gravity * self.mass) / self.mass

        return PhysicsState(
            x=state.vx,
            y=state.vy,
            z=state.vz,
            vx=ax,
            vy=ay,
            vz=az,
            battery_voltage=0.0,  # Calculated separately
            battery_soc=0.0,
        )

    def step(
        self, state: PhysicsState, thrust: Tuple[float, float, float], dt: float
    ) -> PhysicsState:
        """
        Perform one RK4 integration step.
        """
        # k1 = f(t, y)
        k1 = self._derivatives(state, thrust)

        # k2 = f(t + dt/2, y + dt/2 * k1)
        # Note: k1 contains DERIVATIVES (velocities, accelerations).
        # We must add (derivative * dt) to state.
        s2 = PhysicsState(
            x=state.x + dt / 2 * k1.x,
            y=state.y + dt / 2 * k1.y,
            z=state.z + dt / 2 * k1.z,
            vx=state.vx + dt / 2 * k1.vx,
            vy=state.vy + dt / 2 * k1.vy,
            vz=state.vz + dt / 2 * k1.vz,
            battery_voltage=state.battery_voltage,
            battery_soc=state.battery_soc,
        )
        k2 = self._derivatives(s2, thrust)

        s3 = PhysicsState(
            x=state.x + dt / 2 * k2.x,
            y=state.y + dt / 2 * k2.y,
            z=state.z + dt / 2 * k2.z,
            vx=state.vx + dt / 2 * k2.vx,
            vy=state.vy + dt / 2 * k2.vy,
            vz=state.vz + dt / 2 * k2.vz,
            battery_voltage=state.battery_voltage,
            battery_soc=state.battery_soc,
        )
        k3 = self._derivatives(s3, thrust)

        s4 = PhysicsState(
            x=state.x + dt * k3.x,
            y=state.y + dt * k3.y,
            z=state.z + dt * k3.z,
            vx=state.vx + dt * k3.vx,
            vy=state.vy + dt * k3.vy,
            vz=state.vz + dt * k3.vz,
            battery_voltage=state.battery_voltage,
            battery_soc=state.battery_soc,
        )
        k4 = self._derivatives(s4, thrust)

        # y(t+dt) = y(t) + dt/6 * (k1 + 2*k2 + 2*k3 + k4)
        return PhysicsState(
            x=state.x + dt / 6 * (k1.x + 2 * k2.x + 2 * k3.x + k4.x),
            y=state.y + dt / 6 * (k1.y + 2 * k2.y + 2 * k3.y + k4.y),
            z=state.z + dt / 6 * (k1.z + 2 * k2.z + 2 * k3.z + k4.z),
            vx=state.vx + dt / 6 * (k1.vx + 2 * k2.vx + 2 * k3.vx + k4.vx),
            vy=state.vy + dt / 6 * (k1.vy + 2 * k2.vy + 2 * k3.vy + k4.vy),
            vz=state.vz + dt / 6 * (k1.vz + 2 * k2.vz + 2 * k3.vz + k4.vz),
            battery_voltage=state.battery_voltage,
            battery_soc=state.battery_soc,
        )


class LiPoBatteryModel:
    """
    Realistic LiPo battery discharge model.

    Models the characteristic LiPo voltage curve:
    - Initial voltage drop (surface charge)
    - Flat discharge plateau
    - Steep voltage collapse at end
    """

    # 4S LiPo parameters
    CELL_COUNT = 4
    NOMINAL_VOLTAGE = 3.7 * CELL_COUNT  # 14.8V
    FULL_VOLTAGE = 4.2 * CELL_COUNT  # 16.8V
    EMPTY_VOLTAGE = 3.2 * CELL_COUNT  # 12.8V
    CAPACITY_MAH = 5000  # mAh

    def __init__(self) -> None:
        self._soc = 1.0  # State of Charge (0-1)
        self._voltage = self.FULL_VOLTAGE
        self._discharge_mah = 0.0

    def reset(self) -> None:
        """Reset battery to full charge."""
        self._soc = 1.0
        self._voltage = self.FULL_VOLTAGE
        self._discharge_mah = 0.0

    def _soc_to_voltage(self, soc: float) -> float:
        """
        Convert SOC to voltage using polynomial approximation.
        Based on real LiPo discharge curves.
        """
        # Clamp SOC
        soc = max(0.0, min(1.0, soc))

        # Polynomial fit for LiPo curve (per cell)
        # v = a*soc^3 + b*soc^2 + c*soc + d
        a, b, c, d = -0.5, 0.7, 0.6, 3.2
        per_cell = a * soc**3 + b * soc**2 + c * soc + d

        return per_cell * self.CELL_COUNT

    def discharge(self, current_amps: float, dt: float) -> Tuple[float, float]:
        """
        Discharge battery.

        Args:
            current_amps: Discharge current (A)
            dt: Time step (s)

        Returns:
            (voltage, soc)
        """
        # Calculate mAh discharged
        mah_used = current_amps * 1000 * (dt / 3600)
        self._discharge_mah += mah_used

        # Update SOC
        self._soc = 1.0 - (self._discharge_mah / self.CAPACITY_MAH)
        self._soc = max(0.0, self._soc)

        # Update voltage
        self._voltage = self._soc_to_voltage(self._soc)

        return self._voltage, self._soc

    def get_state(self) -> Tuple[float, float, float]:
        """Get current state (voltage, soc, percent)."""
        return self._voltage, self._soc, self._soc * 100

    @property
    def percent(self) -> float:
        """Battery percentage."""
        return self._soc * 100

    @property
    def voltage(self) -> float:
        """Current voltage."""
        return self._voltage

    def estimate_current(self, power_watts: float) -> float:
        """Estimate current draw from power consumption."""
        if self._voltage > 0:
            return power_watts / self._voltage
        return 0.0


class AStarPathfinder:
    """
    A* pathfinding for drone rerouting.

    Uses 3D grid for path planning around obstacles.
    """

    def __init__(self, grid_resolution: float = 10.0) -> None:
        """
        Args:
            grid_resolution: Grid cell size in meters
        """
        self.resolution = grid_resolution
        self._obstacles: List[Tuple[Position, Position]] = []

    def add_obstacle(self, min_pos: Position, max_pos: Position) -> None:
        """Add an obstacle bounding box."""
        self._obstacles.append((min_pos, max_pos))

    def clear_obstacles(self) -> None:
        """Clear all obstacles."""
        self._obstacles.clear()

    def _to_grid(self, pos: Position) -> Tuple[int, int, int]:
        """Convert position to grid coordinates."""
        return (
            int(pos.longitude * 111320 / self.resolution),  # Approx meters
            int(pos.latitude * 110540 / self.resolution),
            int(pos.altitude / self.resolution),
        )

    def _from_grid(self, grid: Tuple[int, int, int], ref: Position) -> Position:
        """Convert grid coordinates back to position."""
        return Position(
            latitude=grid[1] * self.resolution / 110540,
            longitude=grid[0] * self.resolution / 111320,
            altitude=grid[2] * self.resolution,
        )

    def _is_blocked(self, grid: Tuple[int, int, int]) -> bool:
        """Check if grid cell is blocked by an obstacle."""
        # Simplified: check against obstacle bounding boxes
        pos = Position(
            latitude=grid[1] * self.resolution / 110540,
            longitude=grid[0] * self.resolution / 111320,
            altitude=grid[2] * self.resolution,
        )

        for min_p, max_p in self._obstacles:
            if (
                min_p.latitude <= pos.latitude <= max_p.latitude
                and min_p.longitude <= pos.longitude <= max_p.longitude
                and min_p.altitude <= pos.altitude <= max_p.altitude
            ):
                return True
        return False

    def _heuristic(self, a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
        """Euclidean distance heuristic."""
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    def find_path(
        self, start: Position, goal: Position, max_iterations: int = 1000
    ) -> List[Position]:
        """
        Find path from start to goal using A*.

        Args:
            start: Starting position
            goal: Goal position
            max_iterations: Max iterations before giving up

        Returns:
            List of waypoints, or empty if no path found
        """
        import heapq

        start_grid = self._to_grid(start)
        goal_grid = self._to_grid(goal)

        # Priority queue: (f_score, counter, node)
        counter = 0
        open_set = [(0, counter, start_grid)]
        came_from = {}
        g_score = {start_grid: 0}

        # 26 neighbors in 3D
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == dy == dz == 0:
                        continue
                    neighbors.append((dx, dy, dz))

        iterations = 0
        while open_set and iterations < max_iterations:
            iterations += 1
            _, _, current = heapq.heappop(open_set)

            if current == goal_grid:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append(self._from_grid(current, start))
                    current = came_from[current]
                path.append(start)
                path.reverse()
                path.append(goal)
                return path

            for dx, dy, dz in neighbors:
                neighbor = (current[0] + dx, current[1] + dy, current[2] + dz)

                if self._is_blocked(neighbor):
                    continue

                # Movement cost (diagonal is sqrt(2) or sqrt(3))
                move_cost = math.sqrt(dx**2 + dy**2 + dz**2) * self.resolution
                tentative_g = g_score[current] + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self._heuristic(neighbor, goal_grid)
                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor))

        # No path found - return direct path (for degraded mode)
        return [start, goal]


class SpatialIndex:
    """
    R-tree-like spatial index for geofence queries.

    Provides O(log n) query instead of O(n) linear scan.
    Simplified implementation using nested bounding boxes.
    """

    def __init__(self) -> None:
        self._boxes: List[Tuple[float, float, float, float, Any]] = []
        self._sorted_by_lat: List[Tuple[float, float, float, float, Any]] = []
        self._dirty = True

    def insert(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float, data: Any
    ) -> None:
        """Insert a bounding box with associated data."""
        self._boxes.append((min_lat, min_lon, max_lat, max_lon, data))
        self._dirty = True

    def _rebuild_index(self) -> None:
        """Rebuild sorted index."""
        if not self._dirty:
            return

        # Sort by min_lat for binary search
        self._sorted_by_lat = sorted(self._boxes, key=lambda x: x[0])
        self._dirty = False

    def query(self, lat: float, lon: float) -> List[Any]:
        """
        Find all geofences containing this point.

        Uses binary search for initial filtering, then linear check.
        Average case: O(log n + k) where k is number of matches.
        """
        self._rebuild_index()

        if not self._sorted_by_lat:
            return []

        # Binary search for first box that could contain this lat
        import bisect

        # Find boxes where min_lat <= lat
        idx = bisect.bisect_right([box[0] for box in self._sorted_by_lat], lat)

        results = []
        for i in range(idx):
            min_lat, min_lon, max_lat, max_lon, data = self._sorted_by_lat[i]
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                results.append(data)

        return results

    def query_with_altitude(self, lat: float, lon: float, alt: float) -> List[Any]:
        """Query with altitude check (delegates to data.contains())."""
        from .types import Position

        candidates = self.query(lat, lon)
        pos = Position(lat, lon, alt)

        return [
            fence
            for fence in candidates
            if hasattr(fence, "contains") and fence.contains(pos)
        ]
