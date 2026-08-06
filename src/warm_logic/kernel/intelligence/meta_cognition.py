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
[Phase 104.1] Meta-Cognition Engine.
Implements higher-order self-awareness: thinking about thinking.
"""

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("MetaCognition")


@dataclass
class ThoughtRecord:
    """Record of a cognitive event."""

    timestamp: datetime
    category: str  # "reasoning", "planning", "execution", "reflection"
    content: str
    confidence: float
    success: Optional[bool] = None


@dataclass
class CognitiveProfile:
    """Agent's self-model of its cognitive abilities."""

    strengths: List[str]
    weaknesses: List[str]
    biases: List[str]
    learning_rate: float
    reliability: float


class MetaCognitionEngine:
    """
    [Phase 104.1] Meta-Cognition (Thinking about Thinking).

    Capabilities:
    1. Monitor own reasoning processes
    2. Detect cognitive biases
    3. Assess confidence calibration
    4. Introspective self-model
    5. Learning from mistakes
    """

    def __init__(self, history_limit: int = 100):
        self.thought_history: deque = deque(maxlen=history_limit)
        self.profile = self._initialize_profile()
        self.bias_detections: List[Dict] = []
        self.calibration_log: List[Dict] = []
        logger.info("[MetaCognition] Engine Active.")

    def _initialize_profile(self) -> CognitiveProfile:
        """Initialize self-model."""
        return CognitiveProfile(
            strengths=["logical_analysis", "pattern_matching", "code_generation"],
            weaknesses=["real_world_grounding", "temporal_reasoning", "ambiguity"],
            biases=["confirmation_bias", "recency_bias", "anchoring"],
            learning_rate=0.1,
            reliability=0.85,
        )

    def record_thought(
        self, category: str, content: str, confidence: float
    ) -> ThoughtRecord:
        """Record a cognitive event."""
        record = ThoughtRecord(
            timestamp=datetime.now(),
            category=category,
            content=content[:200],
            confidence=confidence,
        )
        self.thought_history.append(record)
        return record

    def update_outcome(self, success: bool):
        """Update the most recent thought with its outcome."""
        if self.thought_history:
            self.thought_history[-1].success = success
            self._update_calibration(self.thought_history[-1])

    def _update_calibration(self, record: ThoughtRecord):
        """Track confidence calibration."""
        self.calibration_log.append(
            {
                "confidence": record.confidence,
                "success": record.success,
                "timestamp": record.timestamp.isoformat(),
            }
        )

    def assess_calibration(self) -> Dict[str, Any]:
        """Assess how well-calibrated confidence estimates are."""
        if len(self.calibration_log) < 5:
            return {"status": "insufficient_data", "entries": len(self.calibration_log)}

        # Group by confidence buckets
        buckets = {"low (0-0.4)": [], "mid (0.4-0.7)": [], "high (0.7-1.0)": []}

        for entry in self.calibration_log:
            conf = entry["confidence"]
            success = 1 if entry["success"] else 0
            if conf < 0.4:
                buckets["low (0-0.4)"].append(success)
            elif conf < 0.7:
                buckets["mid (0.4-0.7)"].append(success)
            else:
                buckets["high (0.7-1.0)"].append(success)

        calibration = {}
        for bucket, outcomes in buckets.items():
            if outcomes:
                calibration[bucket] = {
                    "count": len(outcomes),
                    "success_rate": sum(outcomes) / len(outcomes),
                }

        return {
            "status": "analyzed",
            "calibration": calibration,
            "total_entries": len(self.calibration_log),
        }

    def detect_bias(self, recent_thoughts: int = 10) -> List[Dict]:
        """Detect potential cognitive biases in recent reasoning."""
        detections = []
        recent = list(self.thought_history)[-recent_thoughts:]

        if not recent:
            return []

        # Confirmation bias: Are we only looking at supporting evidence?
        categories = [t.category for t in recent]
        if categories.count("reasoning") > 0.7 * len(recent):
            detections.append(
                {
                    "bias": "confirmation_bias",
                    "evidence": "Heavy focus on reasoning, limited exploration",
                    "severity": 0.6,
                }
            )

        # Recency bias: Over-weighting recent events
        confidences = [t.confidence for t in recent]
        if len(confidences) >= 3 and confidences[-1] > max(confidences[:-1]) + 0.2:
            detections.append(
                {
                    "bias": "recency_bias",
                    "evidence": "Latest thought has disproportionately high confidence",
                    "severity": 0.5,
                }
            )

        # Overconfidence: High confidence with low success rate
        with_outcomes = [t for t in recent if t.success is not None]
        if with_outcomes:
            avg_conf = sum(t.confidence for t in with_outcomes) / len(with_outcomes)
            success_rate = sum(1 for t in with_outcomes if t.success) / len(
                with_outcomes
            )
            if avg_conf > success_rate + 0.2:
                detections.append(
                    {
                        "bias": "overconfidence",
                        "evidence": f"Avg confidence {avg_conf:.2f} > success rate {success_rate:.2f}",
                        "severity": 0.7,
                    }
                )

        self.bias_detections.extend(detections)
        return detections

    def introspect(self) -> Dict[str, Any]:
        """Generate introspective self-report."""
        calibration = self.assess_calibration()
        biases = self.detect_bias()

        recent_categories = {}
        for t in self.thought_history:
            recent_categories[t.category] = recent_categories.get(t.category, 0) + 1

        return {
            "profile": {
                "strengths": self.profile.strengths,
                "weaknesses": self.profile.weaknesses,
                "reliability": self.profile.reliability,
            },
            "thought_count": len(self.thought_history),
            "category_distribution": recent_categories,
            "calibration": calibration,
            "detected_biases": biases,
            "self_awareness_level": "high" if len(biases) > 0 else "baseline",
        }

    def reflect(self, topic: str) -> str:
        """Generate a reflection on a specific topic."""
        reflection_lines = [
            f"# 🧠 Reflection on: {topic}\n",
            f"**Timestamp**: {datetime.now().isoformat()}",
            "",
            "## Self-Assessment",
            f"- **Known Strengths**: {', '.join(self.profile.strengths)}",
            f"- **Known Weaknesses**: {', '.join(self.profile.weaknesses)}",
            f"- **Current Reliability**: {self.profile.reliability:.0%}",
            "",
            "## Cognitive State",
            f"- **Thought History**: {len(self.thought_history)} entries",
            f"- **Bias Detections**: {len(self.bias_detections)} total",
        ]

        # Add calibration if available
        calibration = self.assess_calibration()
        if calibration.get("status") == "analyzed":
            reflection_lines.append("")
            reflection_lines.append("## Confidence Calibration")
            for bucket, data in calibration.get("calibration", {}).items():
                reflection_lines.append(
                    f"- {bucket}: {data['success_rate']:.0%} success ({data['count']} cases)"
                )

        return "\n".join(reflection_lines)


def get_meta_cognition() -> MetaCognitionEngine:
    """Get a new Meta-Cognition engine."""
    return MetaCognitionEngine()
