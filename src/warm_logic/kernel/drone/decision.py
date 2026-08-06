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
[Phase 115.2] Drone Decision Engine.
AI-based autonomous decision making.
Target: < 10ms decision time.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from .types import DroneState, DroneStatus, Threat, Waypoint

logger = logging.getLogger("DroneDecision")


class DecisionType(Enum):
    CONTINUE = "continue"
    AVOID = "avoid"
    RTL = "return_to_launch"
    EMERGENCY = "emergency"
    HOVER = "hover"
    REROUTE = "reroute"


@dataclass
class Decision:
    """A decision made by the AI engine."""

    id: str
    decision_type: DecisionType
    confidence: float
    reasoning: List[str]
    action: Dict[str, Any]
    threats_considered: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


class DroneDecisionEngine:
    """
    [Phase 115.2] AI Decision Engine for Drones.

    Features:
    - Chain-of-Thought reasoning
    - Threat assessment
    - Priority-based decision making
    - Emergency response
    - [v2.0] Bounded memory (max 10K decisions)

    Performance: < 10ms decision latency
    """

    # Decision priorities (higher = more important)
    PRIORITY_EMERGENCY = 100
    PRIORITY_SAFETY = 80
    PRIORITY_MISSION = 50
    PRIORITY_OPTIMIZATION = 20

    # [v2.0] Memory bound
    MAX_HISTORY_SIZE = 10000

    def __init__(self):
        self._decision_counter = 0
        # [v2.0] Bounded deque instead of unbounded list
        self._decision_history: deque = deque(maxlen=self.MAX_HISTORY_SIZE)
        self._active_threats: List[Threat] = []

        # Decision rules (priority, condition, action)
        # [TRUE ] Added reroute check
        self._rules = [
            (100, self._check_emergency, DecisionType.EMERGENCY),
            (90, self._check_low_battery, DecisionType.RTL),
            (80, self._check_geofence_violation, DecisionType.AVOID),
            (75, self._check_reroute_needed, DecisionType.REROUTE),  # [TRUE ]
            (70, self._check_collision_risk, DecisionType.AVOID),
            (60, self._check_weather, DecisionType.HOVER),
            (50, self._check_mission_progress, DecisionType.CONTINUE),
        ]

        logger.info("[DroneDecision] Engine Active.")

    def _gen_decision_id(self) -> str:
        self._decision_counter += 1
        return f"DEC{self._decision_counter:06d}"

    def decide(
        self,
        status: DroneStatus,
        threats: List[Threat] = None,
        mission_waypoints: List[Waypoint] = None,
    ) -> Decision:
        """
        Make autonomous decision based on current state.
        Target latency: < 10ms
        """
        start = time.time()

        threats = threats or []
        self._active_threats = threats

        reasoning = []
        decision_type = DecisionType.CONTINUE
        confidence = 1.0
        action = {}
        threats_considered = [t.id for t in threats]

        # Evaluate rules in priority order
        for priority, check_fn, action_type in self._rules:
            result = check_fn(status, threats)
            if result["triggered"]:
                reasoning.append(f"[P{priority}] {result['reason']}")
                decision_type = action_type
                confidence = result.get("confidence", 0.9)
                action = result.get("action", {})
                break
            else:
                reasoning.append(f"[P{priority}] ✓ {result['reason']}")

        # Default continue decision
        if decision_type == DecisionType.CONTINUE:
            action = {"maintain_course": True}
            reasoning.append("All checks passed. Continue mission.")

        decision = Decision(
            id=self._gen_decision_id(),
            decision_type=decision_type,
            confidence=confidence,
            reasoning=reasoning,
            action=action,
            threats_considered=threats_considered,
        )

        self._decision_history.append(decision)

        elapsed = (time.time() - start) * 1000
        logger.debug(
            f"Decision {decision.id}: {decision_type.value} in {elapsed:.1f}ms"
        )

        return decision

    def _check_emergency(self, status: DroneStatus, threats: List[Threat]) -> Dict:
        """Check for emergency conditions."""
        if status.state == DroneState.EMERGENCY:
            return {
                "triggered": True,
                "reason": "Emergency state detected",
                "confidence": 1.0,
                "action": {"motor_stop": True},
            }

        for threat in threats:
            if threat.severity >= 0.95:
                return {
                    "triggered": True,
                    "reason": f"Critical threat: {threat.description}",
                    "confidence": 0.95,
                    "action": {"emergency_action": threat.recommended_action},
                }

        return {"triggered": False, "reason": "No emergency"}

    def _check_low_battery(self, status: DroneStatus, threats: List[Threat]) -> Dict:
        """Check battery level."""
        if status.battery_percent < 20:
            return {
                "triggered": True,
                "reason": f"Low battery: {status.battery_percent}%",
                "confidence": 0.95,
                "action": {"mode": "rtl"},
            }
        elif status.battery_percent < 30:
            return {
                "triggered": False,
                "reason": f"Battery OK but low: {status.battery_percent}%",
            }
        return {"triggered": False, "reason": f"Battery OK: {status.battery_percent}%"}

    def _check_geofence_violation(
        self, status: DroneStatus, threats: List[Threat]
    ) -> Dict:
        """Check for geofence violations."""
        for threat in threats:
            if threat.threat_type == "geofence":
                return {
                    "triggered": True,
                    "reason": f"Geofence violation: {threat.description}",
                    "confidence": 0.98,
                    "action": {"avoid_direction": threat.recommended_action},
                }
        return {"triggered": False, "reason": "Within geofence"}

    def _check_collision_risk(self, status: DroneStatus, threats: List[Threat]) -> Dict:
        """Check for collision risks."""
        for threat in threats:
            if threat.threat_type in ("obstacle", "aircraft"):
                if threat.severity >= 0.7:
                    return {
                        "triggered": True,
                        "reason": f"Collision risk: {threat.description}",
                        "confidence": 0.9,
                        "action": {
                            "avoid": threat.position.to_dict()
                            if threat.position
                            else None
                        },
                    }
        return {"triggered": False, "reason": "No collision risk"}

    def _check_weather(self, status: DroneStatus, threats: List[Threat]) -> Dict:
        """Check weather conditions."""
        for threat in threats:
            if threat.threat_type == "weather" and threat.severity >= 0.6:
                return {
                    "triggered": True,
                    "reason": f"Weather issue: {threat.description}",
                    "confidence": 0.8,
                    "action": {"hover_and_wait": True},
                }
        return {"triggered": False, "reason": "Weather OK"}

    def _check_reroute_needed(self, status: DroneStatus, threats: List[Threat]) -> Dict:
        """
        [TRUE ] Check if path needs recalculation around obstacles.
        Triggers REROUTE decision for A* pathfinding.
        """
        for threat in threats:
            if threat.threat_type == "obstacle" and 0.5 <= threat.severity < 0.7:
                return {
                    "triggered": True,
                    "reason": f"Obstacle requires reroute: {threat.description}",
                    "confidence": 0.85,
                    "action": {
                        "reroute": True,
                        "obstacle_position": threat.position.to_dict()
                        if threat.position
                        else None,
                    },
                }
        return {"triggered": False, "reason": "No reroute needed"}

    def _check_mission_progress(
        self, status: DroneStatus, threats: List[Threat]
    ) -> Dict:
        """Check mission progress."""
        if status.state == DroneState.FLYING:
            return {
                "triggered": True,
                "reason": "Mission in progress",
                "confidence": 1.0,
                "action": {"continue_mission": True},
            }
        return {"triggered": False, "reason": "Not flying"}

    def assess_threat(self, threat: Threat) -> Dict[str, Any]:
        """Detailed threat assessment."""
        assessment = {
            "threat_id": threat.id,
            "type": threat.threat_type,
            "severity": threat.severity,
            "urgency": "immediate" if threat.severity > 0.8 else "monitor",
            "recommended_action": threat.recommended_action,
        }

        if threat.severity >= 0.9:
            assessment["priority"] = "CRITICAL"
        elif threat.severity >= 0.7:
            assessment["priority"] = "HIGH"
        elif threat.severity >= 0.5:
            assessment["priority"] = "MEDIUM"
        else:
            assessment["priority"] = "LOW"

        return assessment

    def get_decision_history(self, limit: int = 10) -> List[Dict]:
        """Get recent decision history."""
        return [
            {
                "id": d.id,
                "type": d.decision_type.value,
                "confidence": d.confidence,
                "reasoning": d.reasoning[-3:],  # Last 3 reasons
            }
            for d in list(self._decision_history)[-limit:]
        ]
