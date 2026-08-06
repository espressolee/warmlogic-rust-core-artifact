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
[Phase 97.1] Unified Memory Engine.
Integrates Semantic Memory (History) and Vector Vault (Thoughts/Plans) into a single RAG interface.
"""

import logging
from typing import Any, Dict, List, Optional

from warm_logic.kernel.memory.semantic import SemanticMemory
from warm_logic.kernel.memory.vector_vault import VectorVault

logger = logging.getLogger("MemoryEngine")


class MemoryEngine:
    """
    The Hippocampus of WarmLogic.
    Unifies disparate memory systems into a single context retrieval engine.
    """

    def __init__(self, persist_dir: str = "data/memory/vector_store") -> None:
        self.semantic = SemanticMemory(
            persist_dir=persist_dir, collection_name="warmlogic_history"
        )
        self.vault = VectorVault(persist_path=persist_dir)
        logger.info("[MemoryEngine] Cortex Integrated.")

    def store_interaction(
        self, role: str, content: str, session_id: str = "default"
    ) -> None:
        """Store a chat interaction in semantic memory."""
        self.semantic.add(content, role=role, session_id=session_id)

    def store_thought(
        self, thought: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store a reasoning trace."""
        if metadata is None:
            metadata = {}
        self.vault.store_thought(thought, metadata)

    def store_plan(self, goal: str, plan_steps: List[str], outcome: str) -> None:
        """Store a successful plan."""
        self.vault.store_plan(goal, plan_steps, outcome)

    def retrieve_context(self, query: str, max_tokens: int = 4000) -> str:
        """
        Global RAG retrieval.
        Fetches relevant history, past thoughts, and plans to form a comprehensive context.
        """
        # 1. Search Conversation History
        history_hits = self.semantic.search(query, n_results=5)

        # 2. Search Past Thoughts (Simulated via VectorVault query if available,
        #    currently VectorVault returns strings, let's wrap it safe)
        thought_hits = self.vault.query_thoughts(query, n_results=3)

        # 3. Format Context Block
        context_parts = []

        if history_hits:
            context_parts.append("### 📜 Relevant Past Conversations")
            for hit in history_hits:
                role = hit["metadata"].get("role", "unknown").upper()
                content = hit["content"]
                context_parts.append(f"- [{role}] {content}")

        if thought_hits:
            context_parts.append("\n### 🧠 Relevant Past Thoughts")
            for thought in thought_hits:
                context_parts.append(f"- {thought}")

        # TODO: Add Plan retrieval when VectorVault supports querying plans directly by similarity
        # (Current VectorVault implementation separates thoughts/plans but query_thoughts only hits thoughts)

        full_context = "\n".join(context_parts)

        # Simple truncation if too long (rough approx 4 chars/token)
        if len(full_context) > max_tokens * 4:
            full_context = full_context[: max_tokens * 4] + "...(truncated)"

        return full_context

    def sync(self) -> None:
        """Force sync from episodic store if needed."""
        self.semantic.sync_from_episodic()
