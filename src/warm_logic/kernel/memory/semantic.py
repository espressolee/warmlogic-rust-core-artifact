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
[Phase A1: Agent ] Semantic Memory Layer.
Uses ChromaDB for embedding-based similarity search over conversation history.
"""

import hashlib
import logging
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SemanticMemory")

# Lazy import to avoid hard dependency
_CHROMADB = None
_SENTENCE_TRANSFORMERS = None
_chromadb_lock = threading.Lock()
_sentence_transformers_lock = threading.Lock()


def _ensure_chromadb() -> Any:
    """Lazy-load ChromaDB (thread-safe). Returns None if not installed."""
    global _CHROMADB
    if _CHROMADB is None:
        with _chromadb_lock:
            if _CHROMADB is None:  # Double-checked locking
                try:
                    import chromadb

                    _CHROMADB = chromadb
                except ImportError:
                    logger.warning(
                        "ChromaDB not installed. Install with: pip install chromadb"
                    )
                    return None
    return _CHROMADB


def _ensure_sentence_transformers() -> Any:
    """Lazy-load sentence-transformers (thread-safe). Falls back to ChromaDB default."""
    global _SENTENCE_TRANSFORMERS
    if _SENTENCE_TRANSFORMERS is None:
        with _sentence_transformers_lock:
            if _SENTENCE_TRANSFORMERS is None:  # Double-checked locking
                try:
                    from sentence_transformers import SentenceTransformer

                    _SENTENCE_TRANSFORMERS = SentenceTransformer
                except ImportError:
                    logger.info(
                        "sentence-transformers not installed. Using ChromaDB default embeddings."
                    )
                    return None
    return _SENTENCE_TRANSFORMERS


class SemanticMemory:
    """
    Embedding-based semantic memory for WarmLogic.

    Features:
    - Syncs with EpisodicStore (SQLite) for raw conversation storage
    - Indexes all messages in ChromaDB for similarity search
    - Supports both local embeddings (sentence-transformers) and default (mini-lm)
    """

    def __init__(
        self,
        persist_dir: str = ".chromadb",
        collection_name: str = "warmlogic_memory",
        embedding_model: str = "all-MiniLM-L6-v2",
        episodic_db_path: str = "warm_logic.db",
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        self.episodic_db_path = episodic_db_path

        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._embedding_fn: Optional[Any] = None
        self._model: Optional[Any] = None

        self._init_chromadb()

    def _init_chromadb(self) -> None:
        """Initialize ChromaDB client and collection."""
        chromadb = _ensure_chromadb()
        if chromadb is None:
            logger.error("ChromaDB unavailable. Semantic memory disabled.")
            return

        # Use persistent client so data survives restarts
        self._client = chromadb.PersistentClient(path=self.persist_dir)

        # Try to load sentence-transformers for better embeddings
        SentenceTransformer = _ensure_sentence_transformers()
        if SentenceTransformer:
            self._model = SentenceTransformer(self.embedding_model_name)

            class CustomEmbeddingFn:
                def __init__(self, model: Any) -> None:
                    self._model = model

                def __call__(self, input: List[str]) -> List[List[float]]:
                    result: List[List[float]] = self._model.encode(input).tolist()
                    return result

            self._embedding_fn = CustomEmbeddingFn(self._model)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedding_fn,
            )
        else:
            # Use ChromaDB default embedding function
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name
            )

        logger.info(
            f"SemanticMemory initialized: {self._collection.count()} documents indexed."
        )

    def is_available(self) -> bool:
        """Check if semantic memory is operational."""
        return self._collection is not None

    def _generate_id(self, content: str, timestamp: float) -> str:
        """Generate a stable document ID."""
        data = f"{content}:{timestamp}".encode()
        return hashlib.sha256(data).hexdigest()[:16]

    def add(
        self,
        content: str,
        role: str = "user",
        session_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a memory entry to the semantic index.

        Args:
            content: The text content to index.
            role: "user" or "assistant".
            session_id: Optional session identifier.
            metadata: Additional metadata dictionary.

        Returns:
            True if successfully added, False otherwise.
        """
        if not self.is_available():
            return False

        timestamp = time.time()
        doc_id = self._generate_id(content, timestamp)

        doc_metadata = {
            "role": role,
            "session_id": session_id,
            "timestamp": timestamp,
        }
        if metadata:
            doc_metadata.update(metadata)

        if self._collection is None:
            return False
        try:
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[doc_metadata],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add to semantic memory: {e}")
            return False

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_role: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for semantically similar memories.

        Args:
            query: The search query text.
            n_results: Maximum number of results to return.
            filter_role: Optional filter by role ("user" or "assistant").

        Returns:
            List of dictionaries with 'content', 'distance', and 'metadata'.
        """
        if not self.is_available() or self._collection is None:
            return []

        where_filter = None
        if filter_role:
            where_filter = {"role": filter_role}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

        # Parse results into a clean format
        memories = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                memories.append(
                    {
                        "content": doc,
                        "distance": (
                            results["distances"][0][i]
                            if results.get("distances")
                            else None
                        ),
                        "metadata": (
                            results["metadatas"][0][i]
                            if results.get("metadatas")
                            else {}
                        ),
                    }
                )
        return memories

    def sync_from_episodic(self, limit: int = 1000) -> int:
        """
        Sync recent entries from EpisodicStore (SQLite) into ChromaDB.

        Returns:
            Number of new entries indexed.
        """
        if not self.is_available() or self._collection is None:
            return 0

        db_path = Path(self.episodic_db_path)
        if not db_path.exists():
            logger.warning(f"EpisodicStore DB not found: {self.episodic_db_path}")
            return 0

        collection = self._collection  # Local reference for type narrowing
        count = 0
        with closing(sqlite3.connect(self.episodic_db_path)) as conn:
            cursor = conn.execute(
                "SELECT session_id, role, content, timestamp FROM episodes ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            for row in cursor.fetchall():
                session_id, role, content, timestamp = row
                doc_id = self._generate_id(content, timestamp)

                # Check if already indexed
                existing = collection.get(ids=[doc_id])
                if existing["ids"]:
                    continue

                # Add to index
                collection.add(
                    ids=[doc_id],
                    documents=[content],
                    metadatas={
                        "role": role,
                        "session_id": session_id,
                        "timestamp": timestamp,
                    },
                )
                count += 1

        logger.info(f"Synced {count} new entries from EpisodicStore.")
        return count

    def get_context_for_query(self, query: str, max_tokens: int = 4000) -> str:
        """
        Get relevant context for a query, formatted for LLM injection.

        Args:
            query: The user's current query.
            max_tokens: Approximate max characters to return.

        Returns:
            Formatted string of relevant memories.
        """
        memories = self.search(query, n_results=10)
        if not memories:
            return ""

        context_parts = ["[Relevant Memories]"]
        char_count = 0

        for mem in memories:
            entry = f"- [{mem['metadata'].get('role', '?')}] {mem['content']}"
            if char_count + len(entry) > max_tokens:
                break
            context_parts.append(entry)
            char_count += len(entry)

        return "\n".join(context_parts)

    def count(self) -> int:
        """Return the total number of indexed documents."""
        if not self.is_available() or self._collection is None:
            return 0
        return int(self._collection.count())
