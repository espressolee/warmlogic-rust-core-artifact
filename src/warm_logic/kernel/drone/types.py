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
[Phase 115] Drone Common Types.
Core data structures for drone operations.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DroneState(Enum):
    """Drone operational states."""

    IDLE = "idle"
    ARMED = "armed"
    TAKEOFF = "takeoff"
    FLYING = "flying"
    LANDING = "landing"
    EMERGENCY = "emergency"
    RTL = "return_to_launch"  # Return to Launch


class FlightMode(Enum):
    """Flight modes."""

    MANUAL = "manual"
    STABILIZE = "stabilize"
    LOITER = "loiter"
    AUTO = "auto"
    GUIDED = "guided"
    RTL = "rtl"
    LAND = "land"


class AirspaceClass(Enum):
    """Airspace classifications."""

    A = "class_a"  # Controlled, IFR only
    B = "class_b"  # Controlled, major airports
    C = "class_c"  # Controlled, busy airports
    D = "class_d"  # Controlled, small airports
    E = "class_e"  # Controlled, general
    G = "class_g"  # Uncontrolled
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"


@dataclass
class Position:
    """3D position in WGS84 coordinates."""

    latitude: float  # degrees
    longitude: float  # degrees
    altitude: float  # meters MSL

    def distance_to(self, other: "Position") -> float:
        """Haversine distance in meters."""
        R = 6371000  # Earth radius in meters
        lat1, lat2 = math.radians(self.latitude), math.radians(other.latitude)
        dlat = math.radians(other.latitude - self.latitude)
        dlon = math.radians(other.longitude - self.longitude)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        horizontal = R * c
        vertical = abs(other.altitude - self.altitude)
        return math.sqrt(horizontal**2 + vertical**2)

    def to_dict(self) -> Dict[str, float]:
        return {"lat": self.latitude, "lon": self.longitude, "alt": self.altitude}


@dataclass
class Velocity:
    """3D velocity in NED frame."""

    north: float  # m/s
    east: float  # m/s
    down: float  # m/s

    @property
    def speed(self) -> float:
        return math.sqrt(self.north**2 + self.east**2 + self.down**2)


@dataclass
class Attitude:
    """Drone attitude (orientation)."""

    roll: float  # radians
    pitch: float  # radians
    yaw: float  # radians (heading)

    @property
    def heading_degrees(self) -> float:
        return math.degrees(self.yaw) % 360


@dataclass
class Waypoint:
    """Mission waypoint."""

    id: str
    position: Position
    speed: float = 10.0  # m/s
    hold_time: float = 0.0  # seconds
    action: Optional[str] = None  # e.g., "take_photo", "hover"

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "position": self.position.to_dict(),
            "speed": self.speed,
            "hold_time": self.hold_time,
            "action": self.action,
        }


@dataclass
class GeoFence:
    """Geofence boundary."""

    id: str
    name: str
    fence_type: str  # "include" or "exclude"
    vertices: List[Position]  # Polygon vertices
    max_altitude: float = 120.0  # meters
    min_altitude: float = 0.0
    airspace_class: AirspaceClass = AirspaceClass.G

    def contains(self, pos: Position) -> bool:
        """Check if position is inside polygon (ray casting)."""
        if pos.altitude > self.max_altitude or pos.altitude < self.min_altitude:
            return False

        n = len(self.vertices)
        if n < 3:
            return False

        inside = False
        j = n - 1
        for i in range(n):
            vi, vj = self.vertices[i], self.vertices[j]
            if (vi.latitude > pos.latitude) != (
                vj.latitude > pos.latitude
            ) and pos.longitude < (vj.longitude - vi.longitude) * (
                pos.latitude - vi.latitude
            ) / (
                vj.latitude - vi.latitude
            ) + vi.longitude:
                inside = not inside
            j = i
        return inside


@dataclass
class DroneStatus:
    """Complete drone status."""

    timestamp: datetime
    state: DroneState
    mode: FlightMode
    position: Position
    velocity: Velocity
    attitude: Attitude
    battery_percent: float
    gps_satellites: int
    is_armed: bool
    is_connected: bool
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "state": self.state.value,
            "mode": self.mode.value,
            "position": self.position.to_dict(),
            "battery": self.battery_percent,
            "armed": self.is_armed,
            "connected": self.is_connected,
            "errors": self.errors,
        }


@dataclass
class Command:
    """Drone command."""

    id: str
    command_type: str
    params: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0  # Higher = more urgent


@dataclass
class Threat:
    """Detected threat."""

    id: str
    threat_type: str  # "obstacle", "aircraft", "geofence", "weather"
    position: Optional[Position]
    severity: float  # 0.0 to 1.0
    description: str
    recommended_action: str


@dataclass
class HardwareStatus:
    """Hardware health status."""

    timestamp: float
    motors_ok: bool
    sensors_ok: bool
    cpu_temp: float  # Celsius
