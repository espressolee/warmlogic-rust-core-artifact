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
[Phase 106.2] Feedback Memory - Learn from User Corrections.
[Phase 106.3] Preference Tracker - Track User Preferences.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("FeedbackLearning")


@dataclass
class Correction:
    """A user correction/feedback."""

    id: str
    timestamp: datetime
    original: str
    corrected: str
    category: str  # "code", "style", "logic", "format"
    applied: int = 0  # Times this correction was applied


@dataclass
class Preference:
    """A user preference."""

    key: str
    value: Any
    confidence: float  # 0-1, how confident we are
    observations: int
    last_updated: datetime


class FeedbackMemory:
    """
    [Phase 106.2] Feedback-Based Learning.

    Remembers user corrections and applies them in future.
    Runs on CPU. No GPU.

    Examples:
    - "Reply in Korean" → use Korean from then on
    - "Keep the code concise" → generate concise code
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        # GOV-003: Use environment variable for path neutrality
        default_path = os.environ.get("WL_FEEDBACK_PATH", "./data/feedback")
        self.storage_path = storage_path or default_path
        self.corrections: Dict[str, Correction] = {}
        self._counter = 0
        self._load()
        logger.info(
            f"📝 [FeedbackMemory] Active. {len(self.corrections)} corrections loaded."
        )

    def record_correction(
        self, original: str, corrected: str, category: str = "general"
    ) -> Correction:
        """Record a user correction."""
        self._counter += 1
        corr_id = f"COR{self._counter:06d}"

        corr = Correction(
            id=corr_id,
            timestamp=datetime.now(),
            original=original[:200],
            corrected=corrected[:200],
            category=category,
        )

        self.corrections[corr_id] = corr
        self._save()

        logger.info(f"Learned: '{original[:30]}' → '{corrected[:30]}'")
        return corr

    def apply_corrections(self, text: str) -> Tuple[str, List[str]]:
        """Apply known corrections to text."""
        applied = []
        result = text

        for corr in self.corrections.values():
            if corr.original.lower() in result.lower():
                result = result.replace(corr.original, corr.corrected)
                corr.applied += 1
                applied.append(corr.id)

        if applied:
            self._save()

        return result, applied

    def get_category_rules(self, category: str) -> List[Correction]:
        """Get all corrections of a category."""
        return [c for c in self.corrections.values() if c.category == category]

    def _save(self) -> None:
        """Persist to disk."""
        try:
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
            data = {}
            for k, v in self.corrections.items():
                d = asdict(v)
                d["timestamp"] = v.timestamp.isoformat()
                data[k] = d
            with open(f"{self.storage_path}/corrections.json", "w") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Save failed: {e}")

    def _load(self) -> None:
        """Load from disk."""
        try:
            path = f"{self.storage_path}/corrections.json"
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    v["timestamp"] = datetime.fromisoformat(v["timestamp"])
                    self.corrections[k] = Correction(**v)
                self._counter = len(self.corrections)
        except Exception as e:
            logger.debug(f"No data to load: {e}")


class PreferenceTracker:
    """
    [Phase 106.3] Preference Learning.

    Tracks user preferences over time.
    Runs on CPU. No GPU.

    Examples:
    - language: "korean"
    - code_style: "concise"
    - response_length: "short"
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        # GOV-003: Use environment variable for path neutrality
        default_path = os.environ.get("WL_PREFS_PATH", "./data/preferences")
        self.storage_path = storage_path or default_path
        self.preferences: Dict[str, Preference] = {}
        self._load()
        logger.info(
            f"⚙️ [PreferenceTracker] Active. {len(self.preferences)} preferences."
        )

    def observe(self, key: str, value: Any, weight: float = 1.0) -> None:
        """Observe a preference signal."""
        if key in self.preferences:
            pref = self.preferences[key]

            if pref.value == value:
                # Same value observed again - strengthen
                pref.confidence = min(0.99, pref.confidence + 0.1 * weight)
                pref.observations += 1
            else:
                # Different value - update if new evidence is stronger
                if weight > pref.confidence:
                    pref.value = value
                    pref.confidence = 0.5 + (weight * 0.3)
                else:
                    pref.confidence = max(0.1, pref.confidence - 0.1)

            pref.last_updated = datetime.now()
        else:
            # New preference
            self.preferences[key] = Preference(
                key=key,
                value=value,
                confidence=0.5 + (weight * 0.3),
                observations=1,
                last_updated=datetime.now(),
            )

        self._save()

    def get(self, key: str, default: Any = None) -> Tuple[Any, float]:
        """Get a preference value and confidence."""
        if key in self.preferences:
            pref = self.preferences[key]
            return pref.value, pref.confidence
        return default, 0.0

    def get_all(self) -> Dict[str, Any]:
        """Get all preferences."""
        return {
            k: {"value": v.value, "confidence": v.confidence}
            for k, v in self.preferences.items()
        }

    def _save(self) -> None:
        """Persist to disk."""
        try:
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
            data = {}
            for k, v in self.preferences.items():
                d = asdict(v)
                d["last_updated"] = v.last_updated.isoformat()
                data[k] = d
            with open(f"{self.storage_path}/preferences.json", "w") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Save failed: {e}")

    def _load(self) -> None:
        """Load from disk."""
        try:
            path = f"{self.storage_path}/preferences.json"
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    v["last_updated"] = datetime.fromisoformat(v["last_updated"])
                    self.preferences[k] = Preference(**v)
        except Exception as e:
            logger.debug(f"No data to load: {e}")


# Convenience imports
from typing import Tuple


def get_feedback_memory(path: Optional[str] = None) -> FeedbackMemory:
    return FeedbackMemory(path)


def get_preference_tracker(path: Optional[str] = None) -> PreferenceTracker:
    return PreferenceTracker(path)
