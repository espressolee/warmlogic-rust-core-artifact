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
[Phase 102.1] Goal Chaining Engine.
Implements hierarchical goal decomposition and chaining.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("GoalChaining")


class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Goal:
    """A hierarchical goal with sub-goals and dependencies."""

    id: str
    title: str
    description: str
    priority: int = 5  # 1-10, higher = more important
    status: GoalStatus = GoalStatus.PENDING
    parent_id: Optional[str] = None
    sub_goals: List["Goal"] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # IDs of prerequisite goals
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_ready(self) -> bool:
        """Check if all dependencies are satisfied."""
        # In real implementation, would check dependency statuses
        return len(self.dependencies) == 0

    def add_sub_goal(self, title: str, description: str = "") -> "Goal":
        """Add a sub-goal."""
        sub = Goal(
            id=f"{self.id}.{len(self.sub_goals)}",
            title=title,
            description=description,
            parent_id=self.id,
            priority=self.priority,
        )
        self.sub_goals.append(sub)
        return sub


class GoalChainingEngine:
    """
    [Phase 102.1] Hierarchical Goal Management.

    Capabilities:
    1. Goal decomposition (break complex goals into sub-goals)
    2. Dependency tracking (prerequisites)
    3. Priority-based scheduling
    4. Goal chaining (link related goals)
    5. Progress tracking
    """

    def __init__(self) -> None:
        self.goals: Dict[str, Goal] = {}
        self._goal_counter = 0
        logger.info("[GoalChaining] Engine Active.")

    def _generate_id(self) -> str:
        self._goal_counter += 1
        return f"G{self._goal_counter:04d}"

    def create_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 5,
        parent_id: Optional[str] = None,
    ) -> Goal:
        """Create a new goal."""
        goal = Goal(
            id=self._generate_id(),
            title=title,
            description=description,
            priority=priority,
            parent_id=parent_id,
        )
        self.goals[goal.id] = goal

        # Link to parent if exists
        if parent_id and parent_id in self.goals:
            self.goals[parent_id].sub_goals.append(goal)

        logger.info(f"Created goal: {goal.title}")
        return goal

    def decompose(self, goal_id: str, sub_goals: List[str]) -> List[Goal]:
        """Decompose a goal into sub-goals."""
        if goal_id not in self.goals:
            raise ValueError(f"Goal {goal_id} not found")

        parent = self.goals[goal_id]
        created = []

        for i, title in enumerate(sub_goals):
            sub = Goal(
                id=f"{goal_id}.{i}",
                title=title,
                description=f"Sub-goal of {parent.title}",
                parent_id=goal_id,
                priority=parent.priority,
            )
            parent.sub_goals.append(sub)
            self.goals[sub.id] = sub
            created.append(sub)

        logger.info(f"Decomposed {parent.title} into {len(sub_goals)} sub-goals")
        return created

    def add_dependency(self, goal_id: str, depends_on: str) -> None:
        """Add a dependency between goals."""
        if goal_id not in self.goals or depends_on not in self.goals:
            raise ValueError("Goal not found")

        self.goals[goal_id].dependencies.append(depends_on)
        logger.debug(f"Added dependency: {goal_id} depends on {depends_on}")

    def chain(self, goal_ids: List[str]) -> None:
        """Chain goals in sequence (each depends on previous)."""
        for i in range(1, len(goal_ids)):
            self.add_dependency(goal_ids[i], goal_ids[i - 1])
        logger.info(f"Chained {len(goal_ids)} goals")

    def update_status(self, goal_id: str, status: GoalStatus) -> None:
        """Update goal status."""
        if goal_id not in self.goals:
            raise ValueError(f"Goal {goal_id} not found")

        goal = self.goals[goal_id]
        goal.status = status

        if status == GoalStatus.COMPLETED:
            goal.completed_at = datetime.now()

        logger.info(f"{goal.title}: {status.value}")

    def get_next_goals(self, limit: int = 5) -> List[Goal]:
        """Get next actionable goals (ready with no blockers)."""
        ready = []

        for goal in self.goals.values():
            if goal.status not in [GoalStatus.PENDING, GoalStatus.IN_PROGRESS]:
                continue

            # Check dependencies
            deps_satisfied = True
            for dep in goal.dependencies:
                dep_goal = self.goals.get(dep)
                if dep_goal is None or dep_goal.status != GoalStatus.COMPLETED:
                    deps_satisfied = False
                    break

            if deps_satisfied or not goal.dependencies:
                ready.append(goal)

        # Sort by priority
        ready.sort(key=lambda g: (-g.priority, g.created_at))
        return ready[:limit]

    def get_progress(self) -> Dict[str, Any]:
        """Get overall progress statistics."""
        total = len(self.goals)
        completed = sum(
            1 for g in self.goals.values() if g.status == GoalStatus.COMPLETED
        )
        in_progress = sum(
            1 for g in self.goals.values() if g.status == GoalStatus.IN_PROGRESS
        )
        blocked = sum(1 for g in self.goals.values() if g.status == GoalStatus.BLOCKED)

        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "blocked": blocked,
            "pending": total - completed - in_progress - blocked,
            "completion_rate": completed / total * 100 if total > 0 else 0,
        }

    def visualize(self) -> str:
        """Generate a text visualization of the goal tree."""
        lines = ["# 🎯 Goal Hierarchy\n"]

        # Find root goals (no parent)
        roots = [g for g in self.goals.values() if g.parent_id is None]

        def render(goal: Goal, indent: int = 0) -> None:
            status_icon = {
                GoalStatus.PENDING: "⬜",
                GoalStatus.IN_PROGRESS: "🔄",
                GoalStatus.COMPLETED: "✅",
                GoalStatus.BLOCKED: "🚫",
                GoalStatus.FAILED: "❌",
            }.get(goal.status, "⬜")

            prefix = "  " * indent
            lines.append(f"{prefix}{status_icon} [{goal.priority}] {goal.title}")

            for sub in goal.sub_goals:
                render(sub, indent + 1)

        for root in roots:
            render(root)

        return "\n".join(lines)

    def plan_from_objective(self, objective: str, max_depth: int = 3) -> Goal:
        """
        Automatically plan a goal hierarchy from a high-level objective.
        Uses template-based decomposition.
        """
        root = self.create_goal(objective, priority=8)

        # Template-based decomposition
        templates = {
            "implement": [
                "Research existing solutions",
                "Design architecture",
                "Implement core",
                "Test and validate",
            ],
            "optimize": [
                "Measure current performance",
                "Identify bottlenecks",
                "Apply optimizations",
                "Verify improvements",
            ],
            "fix": [
                "Reproduce the issue",
                "Identify root cause",
                "Develop fix",
                "Test fix thoroughly",
            ],
            "create": [
                "Define requirements",
                "Design solution",
                "Build prototype",
                "Refine and finalize",
            ],
            "default": ["Plan approach", "Execute main work", "Verify results"],
        }

        # Select template
        obj_lower = objective.lower()
        template = templates["default"]
        for key, steps in templates.items():
            if key in obj_lower:
                template = steps
                break

        # Create sub-goals
        self.decompose(root.id, template)

        # Chain them
        sub_ids = [s.id for s in root.sub_goals]
        self.chain(sub_ids)

        return root


def get_goal_engine() -> GoalChainingEngine:
    """Get a new Goal Chaining engine."""
    return GoalChainingEngine()
