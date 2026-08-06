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
[Phase 108.4-5] Advanced Online Learning.
Implements online learning and learning scheduler without GPU.
"""

import logging
import math
import random
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("OnlineLearning")


class LearningMode(Enum):
    EXPLORATION = "exploration"
    EXPLOITATION = "exploitation"
    CONSOLIDATION = "consolidation"


@dataclass
class LearningExample:
    """A single learning example."""

    id: str
    input_data: Dict[str, Any]
    output_data: Any
    timestamp: datetime
    importance: float = 1.0
    times_reviewed: int = 0


class OnlineLearner:
    """
    [Phase 108.4] Online Learning System.

    Learns continuously from streaming data without GPU.
    Uses simple nearest-neighbor and weight updates.
    """

    def __init__(self, memory_size: int = 1000):
        self.memory_size = memory_size
        self.examples: deque = deque(maxlen=memory_size)
        self.prototypes: Dict[str, Dict[str, float]] = {}  # Class -> prototype
        self._counter = 0
        self.accuracy_history: deque = deque(maxlen=100)
        logger.info("[OnlineLearner] Active.")

    def _generate_id(self) -> str:
        self._counter += 1
        return f"EX{self._counter:08d}"

    def _to_vector(self, data: Dict[str, Any]) -> List[float]:
        """Convert dict to float vector."""
        values = []
        for k in sorted(data.keys()):
            v = data[k]
            if isinstance(v, (int, float)):
                values.append(float(v))
            elif isinstance(v, bool):
                values.append(1.0 if v else 0.0)
            elif isinstance(v, str):
                values.append(float(hash(v) % 1000) / 1000)
        return values

    def learn(
        self, input_data: Dict[str, Any], label: Any, importance: float = 1.0
    ) -> str:
        """Learn from a single example."""
        ex = LearningExample(
            id=self._generate_id(),
            input_data=input_data,
            output_data=label,
            timestamp=datetime.now(),
            importance=importance,
        )
        self.examples.append(ex)

        # Update prototype
        label_str = str(label)
        vec = self._to_vector(input_data)

        if label_str not in self.prototypes:
            self.prototypes[label_str] = {str(i): v for i, v in enumerate(vec)}
        else:
            # Incremental update
            proto = self.prototypes[label_str]
            for i, v in enumerate(vec):
                key = str(i)
                if key in proto:
                    proto[key] = 0.9 * proto[key] + 0.1 * v
                else:
                    proto[key] = v

        logger.debug(f"Learned: {label}")
        return ex.id

    def predict(self, input_data: Dict[str, Any]) -> Tuple[Any, float]:
        """Predict label for input using nearest prototype."""
        if not self.prototypes:
            return None, 0.0

        vec = self._to_vector(input_data)
        best_label = None
        best_sim = -1.0

        for label, proto in self.prototypes.items():
            proto_vec = [proto.get(str(i), 0.0) for i in range(len(vec))]

            # Cosine similarity
            dot = sum(a * b for a, b in zip(vec, proto_vec))
            norm_v = math.sqrt(sum(a**2 for a in vec))
            norm_p = math.sqrt(sum(b**2 for b in proto_vec))

            if norm_v > 0 and norm_p > 0:
                sim = dot / (norm_v * norm_p)
                if sim > best_sim:
                    best_sim = sim
                    best_label = label

        confidence = (best_sim + 1) / 2  # Normalize to 0-1
        return best_label, confidence

    def evaluate(self, input_data: Dict[str, Any], true_label: Any) -> bool:
        """Evaluate prediction and track accuracy."""
        pred, conf = self.predict(input_data)
        correct = str(pred) == str(true_label)
        self.accuracy_history.append(1 if correct else 0)
        return correct

    def get_accuracy(self) -> float:
        """Get recent accuracy."""
        if not self.accuracy_history:
            return 0.0
        return float(sum(self.accuracy_history)) / len(self.accuracy_history)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "examples": len(self.examples),
            "classes": len(self.prototypes),
            "accuracy": self.get_accuracy(),
        }


class LearningScheduler:
    """
    [Phase 108.5] Learning Scheduler.

    Manages when and what to learn.
    Implements spaced repetition and priority scheduling.
    """

    def __init__(self) -> None:
        self.mode = LearningMode.EXPLORATION
        self.review_queue: List[Tuple[datetime, str, float]] = []
        self.learning_history: deque = deque(maxlen=1000)
        self.mode_schedule = {
            LearningMode.EXPLORATION: 0.4,
            LearningMode.EXPLOITATION: 0.4,
            LearningMode.CONSOLIDATION: 0.2,
        }
        logger.info("⏰ [LearningScheduler] Active.")

    def select_mode(self) -> LearningMode:
        """Select learning mode based on schedule."""
        r = random.random()
        cumulative = 0.0

        for mode, prob in self.mode_schedule.items():
            cumulative += prob
            if r < cumulative:
                self.mode = mode
                return mode

        return LearningMode.EXPLOITATION

    def schedule_review(self, item_id: str, importance: float = 1.0) -> None:
        """Schedule an item for review (spaced repetition)."""
        # Calculate next review time (exponential backoff)
        base_interval = 1  # hours
        times_reviewed = len(
            [h for h in self.learning_history if h.get("id") == item_id]
        )
        interval = base_interval * (2**times_reviewed)

        review_time = datetime.now() + timedelta(hours=interval)
        self.review_queue.append((review_time, item_id, importance))
        self.review_queue.sort(key=lambda x: x[0])

    def get_due_reviews(self, max_items: int = 10) -> List[str]:
        """Get items due for review."""
        now = datetime.now()
        due: List[str] = []

        while self.review_queue and len(due) < max_items:
            if self.review_queue[0][0] <= now:
                _, item_id, _ = self.review_queue.pop(0)
                due.append(item_id)
            else:
                break

        return due

    def prioritize(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize learning items based on various factors."""
        scored = []

        for item in items:
            score = 0.0

            # Importance
            score += item.get("importance", 0.5) * 0.4

            # Recency (newer = higher)
            age = item.get("age_hours", 0)
            score += max(0, 1 - age / 24) * 0.3

            # Difficulty (harder = higher priority)
            score += item.get("difficulty", 0.5) * 0.2

            # Novelty
            score += item.get("novelty", 0.5) * 0.1

            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]

    def log_learning(self, item_id: str, success: bool, duration_ms: int = 0) -> None:
        """Log a learning event."""
        self.learning_history.append(
            {
                "id": item_id,
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "duration_ms": duration_ms,
                "mode": self.mode.value,
            }
        )

    def get_learning_rate(self) -> float:
        """Calculate current learning rate based on recent success."""
        recent = list(self.learning_history)[-50:]
        if not recent:
            return 0.5

        successes = sum(1 for h in recent if h.get("success", False))
        return successes / len(recent)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "pending_reviews": len(self.review_queue),
            "learning_rate": self.get_learning_rate(),
            "total_learned": len(self.learning_history),
        }


class AdvancedLearningSystem:
    """
    Complete Advanced Learning System.

    Combines online learning with smart scheduling.
    """

    def __init__(self) -> None:
        self.learner = OnlineLearner()
        self.scheduler = LearningScheduler()
        logger.info("[AdvancedLearning] System Active.")

    def learn(
        self, input_data: Dict[str, Any], label: Any, importance: float = 1.0
    ) -> Dict[str, Any]:
        """Learn from an example with scheduling."""
        # Select mode
        mode = self.scheduler.select_mode()

        # Learn
        ex_id = self.learner.learn(input_data, label, importance)

        # Schedule review
        self.scheduler.schedule_review(ex_id, importance)

        # Log
        self.scheduler.log_learning(ex_id, True, 0)

        return {
            "id": ex_id,
            "mode": mode.value,
            "learning_rate": self.scheduler.get_learning_rate(),
        }

    def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict with confidence."""
        label, confidence = self.learner.predict(input_data)
        return {"prediction": label, "confidence": confidence}

    def review_session(self, max_items: int = 5) -> List[str]:
        """Run a review session."""
        return self.scheduler.get_due_reviews(max_items)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "learner": self.learner.get_stats(),
            "scheduler": self.scheduler.get_stats(),
        }


def get_learning_system() -> AdvancedLearningSystem:
    """Get an Advanced Learning System."""
    return AdvancedLearningSystem()
