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
[Phase 104.4] Infrastructure Redundancy.
Implements failover, backup, and high-availability patterns.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Redundancy")


class ComponentStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    STANDBY = "standby"


@dataclass
class Component:
    """A redundant system component."""

    id: str
    name: str
    role: str  # "primary", "secondary", "tertiary"
    status: ComponentStatus = ComponentStatus.HEALTHY
    last_heartbeat: datetime = field(default_factory=datetime.now)
    failure_count: int = 0


@dataclass
class Checkpoint:
    """A state checkpoint for recovery."""

    id: str
    timestamp: datetime
    state_hash: str
    data: Dict[str, Any]
    verified: bool = False


class RedundancyManager:
    """
    [Phase 104.4] High-Availability Infrastructure.

    Implements:
    1. Component redundancy (primary/secondary/tertiary)
    2. Automatic failover
    3. State checkpointing
    4. Recovery procedures
    5. Health monitoring
    """

    def __init__(self):
        self.components: Dict[str, Component] = {}
        self.checkpoints: List[Checkpoint] = []
        self.failover_history: List[Dict] = []
        self._setup_default_components()
        logger.info("[Redundancy] Manager Active.")

    def _setup_default_components(self):
        """Setup default redundant components."""
        default_components = [
            ("memory_primary", "Memory Store", "primary"),
            ("memory_secondary", "Memory Store Replica", "secondary"),
            ("safety_primary", "Safety Engine", "primary"),
            ("safety_secondary", "Safety Engine Backup", "secondary"),
            ("inference_primary", "Inference Engine", "primary"),
            ("inference_secondary", "Inference Engine Standby", "standby"),
        ]

        for comp_id, name, role in default_components:
            self.components[comp_id] = Component(
                id=comp_id,
                name=name,
                role=role,
                status=(
                    ComponentStatus.HEALTHY
                    if role != "standby"
                    else ComponentStatus.STANDBY
                ),
            )

    def heartbeat(self, component_id: str) -> bool:
        """Receive heartbeat from a component."""
        if component_id not in self.components:
            return False

        comp = self.components[component_id]
        comp.last_heartbeat = datetime.now()

        # Recovery from degraded state
        if comp.status == ComponentStatus.DEGRADED:
            comp.failure_count = 0
            comp.status = ComponentStatus.HEALTHY
            logger.info(f"[Redundancy] {comp.name} recovered to HEALTHY")

        return True

    def report_failure(self, component_id: str, reason: str = "") -> Dict[str, Any]:
        """Report component failure and trigger failover if needed."""
        if component_id not in self.components:
            return {"success": False, "error": "component_not_found"}

        comp = self.components[component_id]
        comp.failure_count += 1

        # Determine new status
        if comp.failure_count >= 3:
            comp.status = ComponentStatus.FAILED
            logger.warning(
                f"🔁 [Redundancy] {comp.name} FAILED after {comp.failure_count} failures"
            )

            # Trigger failover for primary components
            if comp.role == "primary":
                return self._failover(comp)
        else:
            comp.status = ComponentStatus.DEGRADED
            logger.warning(
                f"🔁 [Redundancy] {comp.name} DEGRADED ({comp.failure_count} failures)"
            )

        return {
            "success": True,
            "component": component_id,
            "status": comp.status.value,
            "failure_count": comp.failure_count,
        }

    def _failover(self, failed_component: Component) -> Dict[str, Any]:
        """Execute failover from primary to secondary."""
        # Find secondary for same component type
        base_name = failed_component.id.replace("_primary", "")
        secondary_id = f"{base_name}_secondary"

        if secondary_id not in self.components:
            logger.error(f"No secondary found for {failed_component.name}")
            return {"success": False, "error": "no_secondary"}

        secondary = self.components[secondary_id]

        # Promote secondary
        secondary.role = "primary"
        secondary.status = ComponentStatus.HEALTHY

        # Demote failed primary
        failed_component.role = "failed_primary"

        failover_record = {
            "timestamp": datetime.now().isoformat(),
            "from": failed_component.id,
            "to": secondary.id,
            "reason": f"Primary failure ({failed_component.failure_count} failures)",
        }
        self.failover_history.append(failover_record)

        logger.info(
            f"🔁 [Redundancy] FAILOVER: {failed_component.name} -> {secondary.name}"
        )

        return {
            "success": True,
            "failover": True,
            "new_primary": secondary.id,
            "old_primary": failed_component.id,
        }

    def checkpoint(self, state: Dict[str, Any]) -> Checkpoint:
        """Create a state checkpoint."""
        state_json = json.dumps(state, sort_keys=True, default=str)
        state_hash = hashlib.sha256(state_json.encode()).hexdigest()[:16]

        checkpoint = Checkpoint(
            id=f"CP{len(self.checkpoints):06d}",
            timestamp=datetime.now(),
            state_hash=state_hash,
            data=state,
            verified=True,
        )

        self.checkpoints.append(checkpoint)

        # Keep only last 10 checkpoints
        if len(self.checkpoints) > 10:
            self.checkpoints = self.checkpoints[-10:]

        logger.debug(f"Checkpoint created: {checkpoint.id}")
        return checkpoint

    def restore(self, checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
        """Restore from a checkpoint."""
        if not self.checkpoints:
            return {"success": False, "error": "no_checkpoints"}

        if checkpoint_id:
            checkpoint = next(
                (c for c in self.checkpoints if c.id == checkpoint_id), None
            )
            if not checkpoint:
                return {"success": False, "error": "checkpoint_not_found"}
        else:
            # Use most recent
            checkpoint = self.checkpoints[-1]

        logger.info(f"[Redundancy] Restoring from {checkpoint.id}")

        return {
            "success": True,
            "checkpoint_id": checkpoint.id,
            "timestamp": checkpoint.timestamp.isoformat(),
            "state": checkpoint.data,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get overall redundancy status."""
        statuses = {}
        for comp in self.components.values():
            statuses[comp.id] = {
                "name": comp.name,
                "role": comp.role,
                "status": comp.status.value,
                "failures": comp.failure_count,
            }

        healthy = sum(
            1 for c in self.components.values() if c.status == ComponentStatus.HEALTHY
        )
        degraded = sum(
            1 for c in self.components.values() if c.status == ComponentStatus.DEGRADED
        )
        failed = sum(
            1 for c in self.components.values() if c.status == ComponentStatus.FAILED
        )

        overall = "healthy"
        if failed > 0:
            overall = "critical"
        elif degraded > 0:
            overall = "degraded"

        return {
            "overall": overall,
            "healthy": healthy,
            "degraded": degraded,
            "failed": failed,
            "total": len(self.components),
            "checkpoints": len(self.checkpoints),
            "failovers": len(self.failover_history),
            "components": statuses,
        }


def get_redundancy() -> RedundancyManager:
    """Get a new Redundancy Manager."""
    return RedundancyManager()
