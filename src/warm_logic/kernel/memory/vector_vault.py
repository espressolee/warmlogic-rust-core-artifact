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
import logging
import os
from typing import Any, Dict, List

import chromadb

logger = logging.getLogger("VectorVault")


class VectorVault:
    """
    [Phase 67] Long-Term Memory (Vector Database).
    Wraps ChromaDB to provide persistent semantic storage for the Sovereign Daemon.
    """

    def __init__(self, persist_path: str = "data/memory/vector_store"):
        self.persist_path = persist_path

        # Ensure directory exists
        os.makedirs(persist_path, exist_ok=True)

        logger.info(f"[VectorVault] Initializing ChromaDB at {persist_path}")

        # Initialize Client
        self.client = chromadb.PersistentClient(path=persist_path)

        # Initialize Collections
        self.thoughts = self.client.get_or_create_collection(name="sovereign_thoughts")
        self.plans = self.client.get_or_create_collection(name="sovereign_plans")

        logger.info(
            f"📚 [VectorVault] Memory Banks Active: Thoughts={self.thoughts.count()}, Plans={self.plans.count()}"
        )

    def store_thought(self, text: str, metadata: Dict[str, Any]):
        """Stores a reasoning trace or insight."""
        import uuid

        try:
            self.thoughts.add(
                documents=[text], metadatas=[metadata], ids=[str(uuid.uuid4())]
            )
            logger.debug(f"[Memory] Stored thought: {text[:50]}...")
        except Exception as e:
            logger.error(f"[Memory] Failed to store thought: {e}")

    def query_thoughts(self, query_text: str, n_results: int = 3) -> List[str]:
        """Retrieves similar past thoughts."""
        try:
            results = self.thoughts.query(query_texts=[query_text], n_results=n_results)
            # Flatten results (list of lists)
            if results and results["documents"]:
                return results["documents"][0]
            return []
        except Exception as e:
            logger.error(f"[Memory] Query failed: {e}")
            return []

    def store_plan(self, goal: str, plan_steps: List[str], outcome: str):
        """Stores a successful plan for future reference."""
        import uuid

        text = f"GOAL: {goal}\nPLAN: {plan_steps}\nOUTCOME: {outcome}"
        metadata = {"goal": goal, "outcome": outcome}
        try:
            self.plans.add(
                documents=[text], metadatas=[metadata], ids=[str(uuid.uuid4())]
            )
            logger.info(f"[Memory] Plan persisted for goal: {goal}")
        except Exception as e:
            logger.error(f"[Memory] Failed to store plan: {e}")

    def wipe_memory(self):
        """Emergency Wipe (for testing mostly)."""
        try:
            self.client.delete_collection("sovereign_thoughts")
            self.client.delete_collection("sovereign_plans")
            logger.warning("[Memory] Wiped all vector data.")
        except Exception as e:
            logger.error(f"[Memory] Wipe failed: {e}")
