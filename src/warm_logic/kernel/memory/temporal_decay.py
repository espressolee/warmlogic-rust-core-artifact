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
[Phase 104.3] Temporal Memory Decay.
Implements time-aware memory with decay and consolidation.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

logger = logging.getLogger("TemporalMemory")


@dataclass
class MemoryItem:
    """A memory with temporal properties."""

    id: str
    content: str
    importance: float  # 0-1
    created_at: datetime
    last_accessed: datetime
    access_count: int = 1
    decay_rate: float = 0.1  # Per day
    consolidated: bool = False


class TemporalMemoryEngine:
    """
    [Phase 104.3] Temporal Memory with Decay.

    Implements:
    1. Time-based forgetting (decay)
    2. Importance-weighted retention
    3. Access-based reinforcement
    4. Memory consolidation
    5. Intelligent retrieval
    """

    def __init__(
        self, base_decay: float = 0.1, consolidation_threshold: int = 5
    ) -> None:
        self.memories: Dict[str, MemoryItem] = {}
        self.base_decay = base_decay
        self.consolidation_threshold = consolidation_threshold
        self._memory_counter = 0
        logger.info("⏳ [TemporalMemory] Engine Active.")

    def _generate_id(self) -> str:
        self._memory_counter += 1
        return f"M{self._memory_counter:06d}"

    def store(self, content: str, importance: float = 0.5) -> MemoryItem:
        """Store a new memory."""
        memory = MemoryItem(
            id=self._generate_id(),
            content=content,
            importance=importance,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            decay_rate=self.base_decay,
        )
        self.memories[memory.id] = memory
        logger.debug(f"Stored memory: {content[:50]}...")
        return memory

    def access(self, memory_id: str) -> Optional[MemoryItem]:
        """Access a memory (reinforces it)."""
        if memory_id not in self.memories:
            return None

        memory = self.memories[memory_id]
        memory.last_accessed = datetime.now()
        memory.access_count += 1

        # Check for consolidation
        if (
            memory.access_count >= self.consolidation_threshold
            and not memory.consolidated
        ):
            self._consolidate(memory)

        return memory

    def _consolidate(self, memory: MemoryItem) -> None:
        """Consolidate a frequently-accessed memory (makes it permanent)."""
        memory.consolidated = True
        memory.decay_rate = 0.01  # Minimal decay
        logger.info(f"⏳ [TemporalMemory] Consolidated: {memory.content[:30]}...")

    def calculate_strength(
        self, memory: MemoryItem, reference_time: Optional[datetime] = None
    ) -> float:
        """Calculate current memory strength after decay."""
        reference_time = reference_time or datetime.now()

        # Time since last access
        time_delta = reference_time - memory.last_accessed
        days_elapsed = time_delta.total_seconds() / 86400

        # Exponential decay with importance modifier
        base_strength = memory.importance
        decay_factor = math.exp(-memory.decay_rate * days_elapsed)

        # Access count bonus
        access_bonus = min(0.3, memory.access_count * 0.05)

        # Consolidated memories have floor
        if memory.consolidated:
            return max(0.5, base_strength * decay_factor + access_bonus)

        return max(0.0, base_strength * decay_factor + access_bonus)

    def retrieve(
        self, query: Optional[str] = None, min_strength: float = 0.1, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve memories above strength threshold."""
        results = []
        now = datetime.now()

        for memory in self.memories.values():
            strength = self.calculate_strength(memory, now)

            if strength >= min_strength:
                # Simple keyword match if query provided
                relevance = 1.0
                if query:
                    query_words = query.lower().split()
                    content_lower = memory.content.lower()
                    matches = sum(1 for w in query_words if w in content_lower)
                    relevance = matches / max(len(query_words), 1)

                results.append(
                    {
                        "id": memory.id,
                        "content": memory.content,
                        "strength": strength,
                        "relevance": relevance,
                        "score": strength * relevance,
                        "consolidated": memory.consolidated,
                        "age_days": (now - memory.created_at).days,
                    }
                )

        # Sort by combined score
        results.sort(key=lambda x: cast(float, x["score"]), reverse=True)
        return results[:limit]

    def prune(self, threshold: float = 0.05) -> int:
        """Remove memories below threshold (forgotten)."""
        now = datetime.now()
        to_remove = []

        for mem_id, memory in self.memories.items():
            if not memory.consolidated:  # Never prune consolidated
                strength = self.calculate_strength(memory, now)
                if strength < threshold:
                    to_remove.append(mem_id)

        for mem_id in to_remove:
            del self.memories[mem_id]

        if to_remove:
            logger.info(f"⏳ [TemporalMemory] Pruned {len(to_remove)} weak memories")

        return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        now = datetime.now()

        if not self.memories:
            return {"total": 0}

        strengths = [self.calculate_strength(m, now) for m in self.memories.values()]
        consolidated = sum(1 for m in self.memories.values() if m.consolidated)

        return {
            "total": len(self.memories),
            "consolidated": consolidated,
            "active": sum(1 for s in strengths if s > 0.3),
            "weak": sum(1 for s in strengths if s < 0.1),
            "avg_strength": sum(strengths) / len(strengths),
            "max_strength": max(strengths),
            "min_strength": min(strengths),
        }

    def simulate_time(self, days: int) -> Dict[str, Any]:
        """Simulate passage of time to see decay effects."""
        now = datetime.now()
        future = now + timedelta(days=days)

        before_stats = self.get_stats()

        # Calculate future strengths
        future_strengths = []
        forgotten = 0

        for memory in self.memories.values():
            strength = self.calculate_strength(memory, future)
            future_strengths.append(strength)
            if strength < 0.05 and not memory.consolidated:
                forgotten += 1

        return {
            "days_simulated": days,
            "before": before_stats,
            "after": {
                "avg_strength": sum(future_strengths) / max(len(future_strengths), 1),
                "will_forget": forgotten,
                "will_remain": len(future_strengths) - forgotten,
            },
        }


def get_temporal_memory() -> TemporalMemoryEngine:
    """Get a new Temporal Memory engine."""
    return TemporalMemoryEngine()
