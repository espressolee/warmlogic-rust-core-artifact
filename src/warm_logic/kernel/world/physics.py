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
[Phase 107.1] Simple Physics Engine.
Implements basic physics simulation without external dependencies.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Physics")


@dataclass
class Vector3:
    """3D vector for physics calculations."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vector3":
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalized(self) -> "Vector3":
        mag = self.magnitude()
        if mag == 0:
            return Vector3(0, 0, 0)
        return Vector3(self.x / mag, self.y / mag, self.z / mag)

    def dot(self, other: "Vector3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z


@dataclass
class PhysicsBody:
    """A physical body in the simulation."""

    id: str
    name: str
    position: Vector3 = field(default_factory=Vector3)
    velocity: Vector3 = field(default_factory=Vector3)
    acceleration: Vector3 = field(default_factory=Vector3)
    mass: float = 1.0
    radius: float = 0.5  # For collision
    is_static: bool = False
    forces: List[Vector3] = field(default_factory=list)


class PhysicsEngine:
    """
    [Phase 107.1] Simple Physics Simulation.

    No external dependencies. Runs on CPU.

    Features:
    1. Newtonian mechanics (F = ma)
    2. Gravity simulation
    3. Collision detection
    4. Projectile motion
    5. Energy conservation
    """

    def __init__(self, gravity: float = -9.81, dt: float = 0.016):
        self.bodies: Dict[str, PhysicsBody] = {}
        self.gravity = Vector3(0, gravity, 0)
        self.dt = dt  # Time step (60 FPS default)
        self.simulation_time = 0.0
        self._counter = 0
        logger.info(f"[Physics] Engine Active. Gravity: {gravity} m/s²")

    def _generate_id(self) -> str:
        self._counter += 1
        return f"PHY{self._counter:06d}"

    def add_body(
        self,
        name: str,
        position: Tuple[float, float, float] = (0, 0, 0),
        velocity: Tuple[float, float, float] = (0, 0, 0),
        mass: float = 1.0,
        radius: float = 0.5,
        is_static: bool = False,
    ) -> PhysicsBody:
        """Add a physics body to the simulation."""
        body = PhysicsBody(
            id=self._generate_id(),
            name=name,
            position=Vector3(*position),
            velocity=Vector3(*velocity),
            mass=mass,
            radius=radius,
            is_static=is_static,
        )
        self.bodies[body.id] = body
        logger.debug(f"Added body: {name} at {position}")
        return body

    def apply_force(self, body_id: str, force: Tuple[float, float, float]):
        """Apply a force to a body."""
        if body_id in self.bodies:
            self.bodies[body_id].forces.append(Vector3(*force))

    def step(self) -> Dict[str, Any]:
        """Advance simulation by one time step."""
        collisions = []

        for body in self.bodies.values():
            if body.is_static:
                continue

            # Sum all forces including gravity
            total_force = self.gravity * body.mass
            for force in body.forces:
                total_force = total_force + force
            body.forces.clear()

            # F = ma → a = F/m
            body.acceleration = total_force * (1.0 / body.mass)

            # Velocity integration
            body.velocity = body.velocity + body.acceleration * self.dt

            # Position integration
            body.position = body.position + body.velocity * self.dt

            # Ground collision (y = 0)
            if body.position.y < body.radius:
                body.position.y = body.radius
                body.velocity.y = -body.velocity.y * 0.7  # Bounce with damping
                collisions.append({"body": body.id, "type": "ground"})

        # Check body-body collisions
        body_list = list(self.bodies.values())
        for i, b1 in enumerate(body_list):
            for b2 in body_list[i + 1 :]:
                if self._check_collision(b1, b2):
                    self._resolve_collision(b1, b2)
                    collisions.append({"body1": b1.id, "body2": b2.id, "type": "body"})

        self.simulation_time += self.dt

        return {
            "time": self.simulation_time,
            "bodies": len(self.bodies),
            "collisions": collisions,
        }

    def _check_collision(self, b1: PhysicsBody, b2: PhysicsBody) -> bool:
        """Check if two bodies are colliding."""
        distance = (b1.position - b2.position).magnitude()
        return distance < (b1.radius + b2.radius)

    def _resolve_collision(self, b1: PhysicsBody, b2: PhysicsBody):
        """Simple elastic collision resolution."""
        if b1.is_static and b2.is_static:
            return

        # Swap velocities (simplified)
        if not b1.is_static and not b2.is_static:
            b1.velocity, b2.velocity = b2.velocity, b1.velocity
        elif b1.is_static:
            b2.velocity = b2.velocity * -0.7
        else:
            b1.velocity = b1.velocity * -0.7

    def simulate(self, duration: float) -> List[Dict]:
        """Simulate for a duration, return trajectory."""
        steps = int(duration / self.dt)
        trajectory = []

        for _ in range(steps):
            result = self.step()
            # Record positions
            positions = {
                bid: (b.position.x, b.position.y, b.position.z)
                for bid, b in self.bodies.items()
            }
            trajectory.append(
                {
                    "time": self.simulation_time,
                    "positions": positions,
                    "collisions": result["collisions"],
                }
            )

        return trajectory

    def predict_landing(self, body_id: str) -> Optional[Dict]:
        """Predict where and when a body will land (y=0)."""
        if body_id not in self.bodies:
            return None

        body = self.bodies[body_id]
        if body.is_static:
            return None

        # Using kinematic equations
        # y = y0 + vy*t + 0.5*g*t²
        # Solve for t when y = radius

        y0 = body.position.y
        vy = body.velocity.y
        g = self.gravity.y

        if g == 0:
            return None

        # Quadratic: 0.5*g*t² + vy*t + (y0 - radius) = 0
        a = 0.5 * g
        b = vy
        c = y0 - body.radius

        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return None

        t1 = (-b + math.sqrt(discriminant)) / (2 * a)
        t2 = (-b - math.sqrt(discriminant)) / (2 * a)

        # Take positive time
        t = max(t1, t2) if min(t1, t2) < 0 else min(t1, t2)
        if t < 0:
            t = max(t1, t2)

        # Predict landing position
        landing_x = body.position.x + body.velocity.x * t
        landing_z = body.position.z + body.velocity.z * t

        return {
            "body": body_id,
            "time_to_land": t,
            "landing_position": (landing_x, body.radius, landing_z),
        }

    def get_energy(self, body_id: str) -> Dict[str, float]:
        """Calculate kinetic and potential energy of a body."""
        if body_id not in self.bodies:
            return {}

        body = self.bodies[body_id]

        # KE = 0.5 * m * v²
        kinetic = 0.5 * body.mass * (body.velocity.magnitude() ** 2)

        # PE = m * g * h
        potential = body.mass * abs(self.gravity.y) * body.position.y

        return {
            "kinetic": kinetic,
            "potential": potential,
            "total": kinetic + potential,
        }

    def get_state(self) -> Dict[str, Any]:
        """Get current simulation state."""
        return {
            "time": self.simulation_time,
            "bodies": {
                bid: {
                    "name": b.name,
                    "position": (b.position.x, b.position.y, b.position.z),
                    "velocity": (b.velocity.x, b.velocity.y, b.velocity.z),
                    "mass": b.mass,
                }
                for bid, b in self.bodies.items()
            },
            "dt": self.dt,
            "gravity": self.gravity.y,
        }


def get_physics_engine(gravity: float = -9.81) -> PhysicsEngine:
    """Get a new Physics Engine."""
    return PhysicsEngine(gravity)
