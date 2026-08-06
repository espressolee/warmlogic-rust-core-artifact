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
[Phase 106.1] Experience Replay - CPU-Based Learning.
Stores and learns from past interactions without GPU.
"""

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ExperienceReplay")


@dataclass
class Experience:
    """A single learning experience."""

    id: str
    timestamp: datetime
    context: str
    action: str
    outcome: str
    success: bool
    reward: float  # -1 to 1
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Pattern:
    """A learned pattern from experiences."""

    id: str
    trigger: str  # What situation triggers this
    response: str  # What to do
    confidence: float
    occurrences: int
    last_success_rate: float


class ExperienceReplayBuffer:
    """
    [Phase 106.1] Experience Replay System.

    Runs on CPU (Mac Mini/MacBook). No GPU required.

    Capabilities:
    1. Store all interactions
    2. Identify patterns from successes/failures
    3. Retrieve relevant past experiences
    4. Incremental pattern learning
    """

    def __init__(
        self, storage_path: Optional[str] = None, max_experiences: int = 10000
    ):
        # GOV-003: Use environment variable for path neutrality
        default_path = os.environ.get("WL_EXPERIENCE_PATH", "./data/experiences")
        self.storage_path = storage_path or default_path
        self.max_experiences = max_experiences
        self.experiences: List[Experience] = []
        self.patterns: Dict[str, Pattern] = {}
        self._exp_counter = 0
        self._pattern_counter = 0

        # Load existing experiences
        self._load_from_disk()
        logger.info(
            f"🧠 [ExperienceReplay] Active. Loaded {len(self.experiences)} experiences."
        )

    def _generate_exp_id(self) -> str:
        self._exp_counter += 1
        return f"EXP{self._exp_counter:08d}"

    def _generate_pattern_id(self) -> str:
        self._pattern_counter += 1
        return f"PAT{self._pattern_counter:06d}"

    def record(
        self,
        context: str,
        action: str,
        outcome: str,
        success: bool,
        reward: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> Experience:
        """Record a new experience."""
        final_reward = reward if reward is not None else (1.0 if success else -0.5)

        exp = Experience(
            id=self._generate_exp_id(),
            timestamp=datetime.now(),
            context=context[:500],
            action=action[:200],
            outcome=outcome[:200],
            success=success,
            reward=final_reward,
            tags=tags or [],
        )

        self.experiences.append(exp)

        # Trim if too many
        if len(self.experiences) > self.max_experiences:
            self.experiences = self.experiences[-self.max_experiences :]

        # Try to learn pattern
        self._attempt_pattern_learning(exp)

        # Periodic save
        if len(self.experiences) % 100 == 0:
            self._save_to_disk()

        logger.debug(f"Recorded: {action[:30]}... -> {'' if success else ''}")
        return exp

    def _attempt_pattern_learning(self, exp: Experience) -> None:
        """Try to learn a pattern from this experience."""
        # Find similar past experiences
        similar = self.recall(exp.context, limit=5)

        if len(similar) < 3:
            return  # Not enough data

        # Check if there's a consistent successful action
        successful = [e for e in similar if e.success]
        if len(successful) >= 2:
            # Check if same action worked multiple times
            actions = [e.action for e in successful]
            from collections import Counter

            common = Counter(actions).most_common(1)

            if common and common[0][1] >= 2:
                action = common[0][0]
                success_rate = len(successful) / len(similar)

                # Create or update pattern
                pattern_key = hashlib.sha256(exp.context[:100].encode()).hexdigest()[
                    :12
                ]

                if pattern_key in self.patterns:
                    # Update existing
                    self.patterns[pattern_key].occurrences += 1
                    self.patterns[pattern_key].last_success_rate = success_rate
                    self.patterns[pattern_key].confidence = min(
                        0.95, self.patterns[pattern_key].confidence + 0.05
                    )
                else:
                    # Create new
                    self.patterns[pattern_key] = Pattern(
                        id=self._generate_pattern_id(),
                        trigger=exp.context[:100],
                        response=action,
                        confidence=0.5 + (success_rate * 0.3),
                        occurrences=len(successful),
                        last_success_rate=success_rate,
                    )
                    logger.info(f"Learned new pattern: {action[:30]}...")

    def recall(self, context: str, limit: int = 10) -> List[Experience]:
        """Recall relevant past experiences based on context similarity."""
        if not self.experiences:
            return []

        # Simple keyword matching (CPU-friendly)
        context_words = set(context.lower().split())

        scored = []
        for exp in self.experiences:
            exp_words = set(exp.context.lower().split())
            overlap = len(context_words & exp_words)
            if overlap > 0:
                score = overlap / max(len(context_words), 1)
                scored.append((score, exp))

        # Sort by relevance
        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:limit]]

    def suggest(self, context: str) -> Optional[Dict[str, Any]]:
        """Suggest an action based on learned patterns."""
        # Check patterns first
        pattern_key = hashlib.sha256(context[:100].encode()).hexdigest()[:12]

        if pattern_key in self.patterns:
            pattern = self.patterns[pattern_key]
            return {
                "source": "pattern",
                "action": pattern.response,
                "confidence": pattern.confidence,
                "occurrences": pattern.occurrences,
            }

        # Fall back to experience recall
        relevant = self.recall(context, limit=3)
        successful = [e for e in relevant if e.success]

        if successful:
            best = max(successful, key=lambda e: e.reward)
            return {
                "source": "experience",
                "action": best.action,
                "confidence": 0.5 + (best.reward * 0.3),
                "from_experience": best.id,
            }

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get learning statistics."""
        if not self.experiences:
            return {"experiences": 0, "patterns": 0}

        successes = sum(1 for e in self.experiences if e.success)
        total = len(self.experiences)

        return {
            "experiences": total,
            "patterns": len(self.patterns),
            "success_rate": successes / total if total > 0 else 0,
            "avg_reward": sum(e.reward for e in self.experiences) / total,
            "tags": list(set(t for e in self.experiences for t in e.tags)),
        }

    def _save_to_disk(self) -> None:
        """Persist experiences to disk."""
        try:
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)

            # Save experiences
            exp_data = []
            for exp in self.experiences[-1000:]:  # Keep last 1000
                exp_dict = asdict(exp)
                exp_dict["timestamp"] = exp.timestamp.isoformat()
                exp_data.append(exp_dict)

            with open(f"{self.storage_path}/experiences.json", "w") as f:
                json.dump(exp_data, f)

            # Save patterns
            pat_data = {k: asdict(v) for k, v in self.patterns.items()}
            with open(f"{self.storage_path}/patterns.json", "w") as f:
                json.dump(pat_data, f)

        except Exception as e:
            logger.warning(f"Failed to save: {e}")

    def _load_from_disk(self) -> None:
        """Load experiences from disk."""
        try:
            exp_file = f"{self.storage_path}/experiences.json"
            if os.path.exists(exp_file):
                with open(exp_file, "r") as f:
                    exp_data = json.load(f)
                for ed in exp_data:
                    ed["timestamp"] = datetime.fromisoformat(ed["timestamp"])
                    self.experiences.append(Experience(**ed))
                self._exp_counter = len(self.experiences)

            pat_file = f"{self.storage_path}/patterns.json"
            if os.path.exists(pat_file):
                with open(pat_file, "r") as f:
                    pat_data = json.load(f)
                for k, pd in pat_data.items():
                    self.patterns[k] = Pattern(**pd)
                self._pattern_counter = len(self.patterns)

        except Exception as e:
            logger.debug(f"No existing data to load: {e}")


def get_experience_buffer(path: Optional[str] = None) -> ExperienceReplayBuffer:
    """Get an Experience Replay buffer."""
    return ExperienceReplayBuffer(path)
