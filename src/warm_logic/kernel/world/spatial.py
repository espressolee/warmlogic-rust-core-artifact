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
[Phase 107.2] Spatial Reasoning Engine.
Implements spatial understanding and reasoning.
"""

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("SpatialReasoning")


class SpatialRelation(Enum):
    """Spatial relationships between objects."""

    ABOVE = "above"
    BELOW = "below"
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    IN_FRONT = "in_front"
    BEHIND = "behind"
    INSIDE = "inside"
    CONTAINS = "contains"
    NEAR = "near"
    FAR = "far"
    TOUCHING = "touching"
    BETWEEN = "between"


@dataclass
class SpatialObject:
    """An object with spatial properties."""

    id: str
    name: str
    position: Tuple[float, float, float]  # x, y, z
    size: Tuple[float, float, float]  # width, height, depth
    category: str = "object"


class SpatialReasoner:
    """
    [Phase 107.2] Spatial Reasoning Engine.

    Understands and reasons about spatial relationships.

    Features:
    1. Spatial relation detection
    2. Distance calculation
    3. Containment checking
    4. Path finding (basic)
    5. Spatial queries
    """

    def __init__(self, near_threshold: float = 2.0) -> None:
        self.objects: Dict[str, SpatialObject] = {}
        self.near_threshold = near_threshold
        self._counter = 0
        logger.info("[SpatialReasoning] Engine Active.")

    def _generate_id(self) -> str:
        self._counter += 1
        return f"SPT{self._counter:06d}"

    def add_object(
        self,
        name: str,
        position: Tuple[float, float, float],
        size: Tuple[float, float, float] = (1, 1, 1),
        category: str = "object",
    ) -> SpatialObject:
        """Add a spatial object."""
        obj = SpatialObject(
            id=self._generate_id(),
            name=name,
            position=position,
            size=size,
            category=category,
        )
        self.objects[obj.id] = obj
        return obj

    def distance(self, obj1_id: str, obj2_id: str) -> Optional[float]:
        """Calculate Euclidean distance between two objects."""
        if obj1_id not in self.objects or obj2_id not in self.objects:
            return None

        p1 = self.objects[obj1_id].position
        p2 = self.objects[obj2_id].position

        return math.sqrt(
            (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2
        )

    def get_relation(self, obj1_id: str, obj2_id: str) -> List[SpatialRelation]:
        """Determine spatial relations between two objects."""
        if obj1_id not in self.objects or obj2_id not in self.objects:
            return []

        o1 = self.objects[obj1_id]
        o2 = self.objects[obj2_id]
        relations = []

        # Vertical relations (y-axis)
        if o1.position[1] > o2.position[1] + o2.size[1] / 2:
            relations.append(SpatialRelation.ABOVE)
        elif o1.position[1] < o2.position[1] - o2.size[1] / 2:
            relations.append(SpatialRelation.BELOW)

        # Horizontal relations (x-axis)
        if o1.position[0] < o2.position[0] - o2.size[0] / 2:
            relations.append(SpatialRelation.LEFT_OF)
        elif o1.position[0] > o2.position[0] + o2.size[0] / 2:
            relations.append(SpatialRelation.RIGHT_OF)

        # Depth relations (z-axis)
        if o1.position[2] > o2.position[2] + o2.size[2] / 2:
            relations.append(SpatialRelation.IN_FRONT)
        elif o1.position[2] < o2.position[2] - o2.size[2] / 2:
            relations.append(SpatialRelation.BEHIND)

        # Distance-based relations
        dist = self.distance(obj1_id, obj2_id)
        if dist is not None:
            if dist < self.near_threshold:
                relations.append(SpatialRelation.NEAR)
            else:
                relations.append(SpatialRelation.FAR)

            # Touching check
            touch_dist = (
                math.sqrt(sum(s**2 for s in o1.size)) / 2
                + math.sqrt(sum(s**2 for s in o2.size)) / 2
            )
            if dist <= touch_dist:
                relations.append(SpatialRelation.TOUCHING)

        # Containment check
        if self._is_inside(o1, o2):
            relations.append(SpatialRelation.INSIDE)
        if self._is_inside(o2, o1):
            relations.append(SpatialRelation.CONTAINS)

        return relations

    def _is_inside(self, inner: SpatialObject, outer: SpatialObject) -> bool:
        """Check if inner object is inside outer object."""
        for i in range(3):
            inner_min = inner.position[i] - inner.size[i] / 2
            inner_max = inner.position[i] + inner.size[i] / 2
            outer_min = outer.position[i] - outer.size[i] / 2
            outer_max = outer.position[i] + outer.size[i] / 2

            if inner_min < outer_min or inner_max > outer_max:
                return False
        return True

    def query(
        self, query_type: str, params: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Run a spatial query."""
        params = params or {}
        results = []

        if query_type == "near":
            ref_id = params.get("reference")
            if ref_id in self.objects:
                for oid in self.objects:
                    if oid != ref_id:
                        dist = self.distance(ref_id, oid)
                        if dist and dist < self.near_threshold:
                            results.append(oid)

        elif query_type == "above":
            ref_id = params.get("reference")
            if ref_id in self.objects:
                ref_y = self.objects[ref_id].position[1]
                for oid, obj in self.objects.items():
                    if oid != ref_id and obj.position[1] > ref_y:
                        results.append(oid)

        elif query_type == "in_region":
            min_pos = params.get("min", (-math.inf, -math.inf, -math.inf))
            max_pos = params.get("max", (math.inf, math.inf, math.inf))
            for oid, obj in self.objects.items():
                if all(min_pos[i] <= obj.position[i] <= max_pos[i] for i in range(3)):
                    results.append(oid)

        elif query_type == "by_category":
            category = params.get("category")
            for oid, obj in self.objects.items():
                if obj.category == category:
                    results.append(oid)

        return results

    def find_between(self, obj1_id: str, obj2_id: str) -> List[str]:
        """Find objects between two reference objects."""
        if obj1_id not in self.objects or obj2_id not in self.objects:
            return []

        p1 = self.objects[obj1_id].position
        p2 = self.objects[obj2_id].position

        # Find center point and threshold
        center = tuple((p1[i] + p2[i]) / 2 for i in range(3))
        dist = self.distance(obj1_id, obj2_id)
        max_dist = dist / 2 if dist is not None else 0.0

        between = []
        for oid, obj in self.objects.items():
            if oid in (obj1_id, obj2_id):
                continue

            # Check if object is roughly between
            dist_to_center = math.sqrt(
                sum((obj.position[i] - center[i]) ** 2 for i in range(3))
            )
            if dist_to_center < max_dist:
                between.append(oid)

        return between

    def describe_scene(self) -> str:
        """Generate natural language description of the scene."""
        if not self.objects:
            return "The scene is empty."

        lines = [f"Scene contains {len(self.objects)} objects:"]

        for obj in self.objects.values():
            lines.append(
                f"  - {obj.name} ({obj.category}) at ({obj.position[0]:.1f}, {obj.position[1]:.1f}, {obj.position[2]:.1f})"
            )

        # Add some relations
        obj_list = list(self.objects.values())
        if len(obj_list) >= 2:
            lines.append("\nRelationships:")
            for i, o1 in enumerate(obj_list[:3]):  # Limit to first 3
                for o2 in obj_list[i + 1 : 4]:
                    rels = self.get_relation(o1.id, o2.id)
                    if rels:
                        rel_names = [r.value for r in rels[:3]]
                        lines.append(
                            f"  - {o1.name} is {', '.join(rel_names)} {o2.name}"
                        )

        return "\n".join(lines)

    def can_reach(
        self, from_id: str, to_id: str, obstacles: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Check if a straight-line path exists between two objects."""
        if from_id not in self.objects or to_id not in self.objects:
            return {"reachable": False, "reason": "object_not_found"}

        obstacles = obstacles or []

        p1 = self.objects[from_id].position
        p2 = self.objects[to_id].position

        # Simple line-of-sight check
        for obs_id in obstacles:
            if obs_id not in self.objects:
                continue

            obs = self.objects[obs_id]
            # Check if obstacle is between start and end
            between = self.find_between(from_id, to_id)
            if obs_id in between:
                return {"reachable": False, "reason": "blocked", "blocker": obs.name}

        return {"reachable": True, "distance": self.distance(from_id, to_id)}

    def get_stats(self) -> Dict[str, Any]:
        """Get scene statistics."""
        categories: Dict[str, int] = {}
        for obj in self.objects.values():
            categories[obj.category] = categories.get(obj.category, 0) + 1

        return {"objects": len(self.objects), "categories": categories}


def get_spatial_reasoner() -> SpatialReasoner:
    """Get a new Spatial Reasoner."""
    return SpatialReasoner()
