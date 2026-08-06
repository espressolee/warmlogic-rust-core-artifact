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
[Phase 103.2] Adaptive Replanning Engine.
Implements dynamic goal adjustment based on feedback and progress.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AdaptiveReplan")


class ReplanTrigger(Enum):
    """Reasons for triggering a replan."""

    GOAL_BLOCKED = "goal_blocked"
    NEW_INFORMATION = "new_information"
    PRIORITY_CHANGE = "priority_change"
    DEADLINE_RISK = "deadline_risk"
    RESOURCE_CHANGE = "resource_change"
    FAILURE = "failure"


@dataclass
class PlanRevision:
    """A record of a plan change."""

    timestamp: datetime
    trigger: ReplanTrigger
    original_plan: str
    revised_plan: str
    reason: str
    impact_score: float  # 0-1, higher = more significant


class AdaptiveReplanner:
    """
    [Phase 103.2] Adaptive Replanning.

    Capabilities:
    1. Monitor plan execution for blockers
    2. Detect when replanning is needed
    3. Generate alternative approaches
    4. Smoothly transition to new plan
    """

    def __init__(self, goal_engine: Any = None) -> None:
        self.goal_engine = goal_engine
        self.revisions: List[PlanRevision] = []
        self.execution_log: List[Dict[str, Any]] = []
        self.blocked_goals: List[str] = []
        logger.info("[AdaptiveReplan] Engine Active.")

    def log_execution(
        self, goal_id: str, status: str, details: str = "", success: bool = True
    ) -> None:
        """Log a goal execution attempt."""
        self.execution_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "goal_id": goal_id,
                "status": status,
                "details": details,
                "success": success,
            }
        )

        if not success:
            self.blocked_goals.append(goal_id)

    def detect_replan_need(self) -> Optional[Dict[str, Any]]:
        """Detect if replanning is needed based on execution history."""
        triggers: List[Dict[str, Any]] = []

        # Check for blocked goals
        if self.blocked_goals:
            triggers.append(
                {
                    "trigger": ReplanTrigger.GOAL_BLOCKED,
                    "details": f"{len(self.blocked_goals)} goals blocked",
                    "urgency": 0.8,
                }
            )

        # Check failure rate
        if len(self.execution_log) >= 3:
            recent = self.execution_log[-5:]
            failure_rate = sum(1 for e in recent if not e["success"]) / len(recent)
            if failure_rate > 0.4:
                triggers.append(
                    {
                        "trigger": ReplanTrigger.FAILURE,
                        "details": f"High failure rate: {failure_rate:.0%}",
                        "urgency": 0.9,
                    }
                )

        if not triggers:
            return None

        # Return most urgent trigger
        most_urgent = max(triggers, key=lambda t: float(t.get("urgency", 0)))
        trigger_enum = most_urgent["trigger"]
        trigger_value = (
            trigger_enum.value
            if isinstance(trigger_enum, ReplanTrigger)
            else str(trigger_enum)
        )
        return {
            "needs_replan": True,
            "primary_trigger": trigger_value,
            "details": most_urgent["details"],
            "all_triggers": [
                (
                    t["trigger"].value
                    if isinstance(t["trigger"], ReplanTrigger)
                    else str(t["trigger"])
                )
                for t in triggers
            ],
        }

    def generate_alternatives(self, blocked_goal: str) -> List[Dict[str, Any]]:
        """Generate alternative approaches for a blocked goal."""
        alternatives = [
            {
                "id": "alt_decompose",
                "name": "Decompose into smaller steps",
                "description": "Split the goal into smaller, achievable units.",
                "success_probability": 0.7,
            },
            {
                "id": "alt_dependency",
                "name": "Bypass dependency",
                "description": "Find an alternative path around the blocked dependency.",
                "success_probability": 0.6,
            },
            {
                "id": "alt_resource",
                "name": "Reallocate resources",
                "description": "Use a different resource or tool.",
                "success_probability": 0.65,
            },
            {
                "id": "alt_defer",
                "name": "Defer and retry",
                "description": "Handle other goals first and retry later.",
                "success_probability": 0.5,
            },
            {
                "id": "alt_negotiate",
                "name": "Revise goal",
                "description": "Revise the original goal into an achievable form.",
                "success_probability": 0.8,
            },
        ]

        return alternatives

    def replan(
        self, trigger: ReplanTrigger, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a replan operation."""
        context = context or {}
        logger.info(f"[AdaptiveReplan] Replanning due to: {trigger.value}")

        # Generate new plan based on trigger
        if trigger == ReplanTrigger.GOAL_BLOCKED:
            blocked = self.blocked_goals[-1] if self.blocked_goals else "unknown"
            alternatives = self.generate_alternatives(blocked)
            best_alt = max(
                alternatives, key=lambda a: float(a.get("success_probability", 0))
            )

            revision = PlanRevision(
                timestamp=datetime.now(),
                trigger=trigger,
                original_plan=f"Execute goal: {blocked}",
                revised_plan=f"Apply strategy: {best_alt['name']}",
                reason=f"Goal blocked, applying {best_alt['name']}",
                impact_score=float(best_alt["success_probability"]),
            )

        elif trigger == ReplanTrigger.FAILURE:
            revision = PlanRevision(
                timestamp=datetime.now(),
                trigger=trigger,
                original_plan="Continue current execution",
                revised_plan="Pause, analyze failures, retry with modifications",
                reason="High failure rate detected",
                impact_score=0.7,
            )

        else:
            revision = PlanRevision(
                timestamp=datetime.now(),
                trigger=trigger,
                original_plan=context.get("original", "Previous plan"),
                revised_plan=context.get("revised", "Re-evaluate and adjust"),
                reason=context.get("reason", f"Triggered by {trigger.value}"),
                impact_score=0.5,
            )

        self.revisions.append(revision)

        # Clear blocked goals after replanning
        self.blocked_goals = []

        return {
            "status": "replanned",
            "trigger": trigger.value,
            "new_plan": revision.revised_plan,
            "impact_score": revision.impact_score,
            "total_revisions": len(self.revisions),
        }

    def get_adaptation_stats(self) -> Dict[str, Any]:
        """Get statistics on planning adaptations."""
        if not self.revisions:
            return {"total_revisions": 0, "avg_impact": 0}

        return {
            "total_revisions": len(self.revisions),
            "avg_impact": sum(r.impact_score for r in self.revisions)
            / len(self.revisions),
            "triggers": [r.trigger.value for r in self.revisions],
            "execution_attempts": len(self.execution_log),
            "success_rate": sum(1 for e in self.execution_log if e["success"])
            / max(len(self.execution_log), 1),
        }

    def summarize(self) -> str:
        """Get human-readable summary."""
        stats = self.get_adaptation_stats()

        lines = [
            "# 🔄 Adaptive Replanning Summary\n",
            f"**Total Revisions**: {stats['total_revisions']}",
            f"**Execution Attempts**: {stats['execution_attempts']}",
            f"**Success Rate**: {stats['success_rate']:.0%}",
            "",
            "## Recent Revisions",
        ]

        for rev in self.revisions[-5:]:
            lines.append(f"- [{rev.trigger.value}] {rev.reason}")

        return "\n".join(lines)


def get_replanner() -> AdaptiveReplanner:
    """Get a new Adaptive Replanner instance."""
    return AdaptiveReplanner()
