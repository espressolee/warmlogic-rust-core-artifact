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
[Phase 101.2] Enhanced Self-Awareness: State Diff Engine.
Tracks and reports changes in agent state over time.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("StateDiff")


@dataclass
class StateSnapshot:
    """A snapshot of agent state at a point in time."""

    timestamp: datetime
    state_hash: str
    memory_count: int
    tools_available: List[str]
    active_goals: List[str]
    error_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class StateDiffEngine:
    """
    [Phase 101.2] State Diff Engine for Self-Awareness.

    Capabilities:
    1. Capture current state snapshot
    2. Compare snapshots to detect changes
    3. Track errors and their patterns
    4. Report state transitions
    """

    def __init__(self) -> None:
        self.snapshots: List[StateSnapshot] = []
        self.errors: List[Dict[str, Any]] = []
        self._max_snapshots = 100
        logger.info("[StateDiff] Self-Awareness Engine Active.")

    def capture_snapshot(
        self,
        memory: Optional[Any] = None,
        tools: Optional[Any] = None,
        goals: Optional[List[str]] = None,
    ) -> StateSnapshot:
        """Capture current state as a snapshot."""

        # Gather state info
        memory_count: int = 0
        if memory:
            try:
                if hasattr(memory, "semantic") and memory.semantic:
                    collection = getattr(memory.semantic, "_collection", None)
                    if collection is not None and hasattr(collection, "count"):
                        memory_count = int(collection.count())
                    else:
                        memory_count = 0
            except Exception:
                pass

        tools_list = []
        if tools:
            try:
                tools_list = list(tools.tools.keys())
            except Exception:
                pass

        # Create state dict for hashing
        state_dict = {
            "memory_count": memory_count,
            "tools": sorted(tools_list),
            "goals": sorted(goals or []),
            "error_count": len(self.errors),
        }

        state_hash = hashlib.sha256(
            json.dumps(state_dict, sort_keys=True).encode()
        ).hexdigest()[:16]

        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            state_hash=state_hash,
            memory_count=memory_count,
            tools_available=tools_list,
            active_goals=goals or [],
            error_count=len(self.errors),
        )

        self.snapshots.append(snapshot)

        # Prune old snapshots
        if len(self.snapshots) > self._max_snapshots:
            self.snapshots = self.snapshots[-self._max_snapshots :]

        logger.debug(f"Snapshot captured: {state_hash}")
        return snapshot

    def record_error(self, error: Exception, context: str = "") -> None:
        """Record an error for pattern analysis."""
        self.errors.append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": type(error).__name__,
                "message": str(error),
                "context": context,
            }
        )
        logger.warning(f"Error recorded: {type(error).__name__}")

    def diff(
        self,
        snapshot1: Optional[StateSnapshot] = None,
        snapshot2: Optional[StateSnapshot] = None,
    ) -> Dict[str, Any]:
        """Compare two snapshots and report differences."""

        if len(self.snapshots) < 2:
            return {"status": "insufficient_snapshots", "changes": []}

        s1 = snapshot1 or self.snapshots[-2]
        s2 = snapshot2 or self.snapshots[-1]

        changes = []

        # Memory changes
        if s1.memory_count != s2.memory_count:
            delta = s2.memory_count - s1.memory_count
            changes.append(
                {
                    "type": "memory",
                    "from": s1.memory_count,
                    "to": s2.memory_count,
                    "delta": delta,
                    "description": f"Memory {'grew' if delta > 0 else 'shrunk'} by {abs(delta)}",
                }
            )

        # Tool changes
        tools_added = set(s2.tools_available) - set(s1.tools_available)
        tools_removed = set(s1.tools_available) - set(s2.tools_available)

        if tools_added:
            changes.append(
                {
                    "type": "tools_added",
                    "items": list(tools_added),
                    "description": f"New tools: {', '.join(tools_added)}",
                }
            )

        if tools_removed:
            changes.append(
                {
                    "type": "tools_removed",
                    "items": list(tools_removed),
                    "description": f"Removed tools: {', '.join(tools_removed)}",
                }
            )

        # Goal changes
        goals_added = set(s2.active_goals) - set(s1.active_goals)
        goals_completed = set(s1.active_goals) - set(s2.active_goals)

        if goals_added:
            changes.append(
                {
                    "type": "goals_added",
                    "items": list(goals_added),
                    "description": f"New goals: {', '.join(goals_added)}",
                }
            )

        if goals_completed:
            changes.append(
                {
                    "type": "goals_completed",
                    "items": list(goals_completed),
                    "description": f"Completed: {', '.join(goals_completed)}",
                }
            )

        # Error changes
        error_delta = s2.error_count - s1.error_count
        if error_delta > 0:
            changes.append(
                {
                    "type": "errors",
                    "delta": error_delta,
                    "description": f"{error_delta} new error(s) occurred",
                }
            )

        return {
            "status": "compared",
            "from_timestamp": s1.timestamp.isoformat(),
            "to_timestamp": s2.timestamp.isoformat(),
            "state_changed": s1.state_hash != s2.state_hash,
            "changes": changes,
        }

    def analyze_errors(self) -> Dict[str, Any]:
        """Analyze error patterns for self-improvement."""
        if not self.errors:
            return {"status": "no_errors", "patterns": []}

        # Count by type
        type_counts: Dict[str, int] = {}
        for err in self.errors:
            t = err["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        patterns = []
        for error_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            patterns.append(
                {
                    "type": error_type,
                    "count": count,
                    "percentage": count / len(self.errors) * 100,
                }
            )

        return {
            "status": "analyzed",
            "total_errors": len(self.errors),
            "patterns": patterns,
            "most_common": patterns[0]["type"] if patterns else None,
        }

    def summarize(self) -> str:
        """Generate human-readable state summary."""
        if not self.snapshots:
            return "No state snapshots available."

        latest = self.snapshots[-1]
        error_analysis = self.analyze_errors()

        lines = [
            "# 📊 Agent State Summary\n",
            f"**Last Updated**: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**State Hash**: `{latest.state_hash}`\n",
            "## Current State",
            f"- Memory Items: {latest.memory_count}",
            f"- Tools Available: {len(latest.tools_available)} ({', '.join(latest.tools_available[:3])}...)",
            f"- Active Goals: {len(latest.active_goals)}",
            f"- Total Snapshots: {len(self.snapshots)}",
            "",
            "## Error Analysis",
            f"- Total Errors: {error_analysis['total_errors']}",
        ]

        if error_analysis.get("most_common"):
            lines.append(f"- Most Common: {error_analysis['most_common']}")

        return "\n".join(lines)


def get_state_diff() -> StateDiffEngine:
    """Get a new StateDiff engine instance."""
    return StateDiffEngine()
