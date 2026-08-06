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
# Korean tokens below (stopwords, triple-extraction regexes, and the [가-힣] entity
# class) are matched against input text. They are NLP data, not prose — do not translate.

"""
[Phase 102.2] GraphRAG - Graph-Enhanced Retrieval.
Implements knowledge graph integration with RAG.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("GraphRAG")


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph."""

    id: str
    label: str
    type: str  # "concept", "entity", "event", "fact"
    properties: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class KnowledgeEdge:
    """An edge (relationship) in the knowledge graph."""

    source_id: str
    target_id: str
    relation: str  # "is_a", "has", "related_to", "causes", etc.
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class GraphRAG:
    """
    [Phase 102.2] Graph-Enhanced RAG.

    Combines:
    1. Knowledge Graph for structured relationships
    2. Vector similarity for semantic search
    3. Graph traversal for multi-hop reasoning
    """

    def __init__(self, memory_engine=None):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: List[KnowledgeEdge] = []
        self.memory = memory_engine
        self._adj_list: Dict[str, List[Tuple[str, str, float]]] = (
            {}
        )  # node_id -> [(target, relation, weight)]
        logger.info("[GraphRAG] Knowledge Graph Active.")

    def add_node(
        self, label: str, node_type: str = "concept", properties: Dict = None
    ) -> KnowledgeNode:
        """Add a node to the knowledge graph."""
        node_id = f"N{len(self.nodes):05d}"
        node = KnowledgeNode(
            id=node_id, label=label, type=node_type, properties=properties or {}
        )
        self.nodes[node_id] = node
        self._adj_list[node_id] = []
        logger.debug(f"Added node: {label}")
        return node

    def add_edge(
        self, source_label: str, relation: str, target_label: str, weight: float = 1.0
    ) -> Optional[KnowledgeEdge]:
        """Add an edge between nodes (creates nodes if needed)."""
        # Find or create source
        source = self._find_node(source_label)
        if not source:
            source = self.add_node(source_label)

        # Find or create target
        target = self._find_node(target_label)
        if not target:
            target = self.add_node(target_label)

        edge = KnowledgeEdge(
            source_id=source.id, target_id=target.id, relation=relation, weight=weight
        )
        self.edges.append(edge)
        self._adj_list[source.id].append((target.id, relation, weight))

        logger.debug(f"Added edge: {source_label} --{relation}--> {target_label}")
        return edge

    def _find_node(self, label: str) -> Optional[KnowledgeNode]:
        """Find a node by label."""
        for node in self.nodes.values():
            if node.label.lower() == label.lower():
                return node
        return None

    def get_neighbors(self, node_label: str, max_hops: int = 1) -> List[Dict]:
        """Get neighboring nodes up to max_hops away."""
        start = self._find_node(node_label)
        if not start:
            return []

        visited = {start.id}
        result = []
        current = [(start.id, 0)]

        while current:
            node_id, depth = current.pop(0)

            if depth >= max_hops:
                continue

            for target_id, relation, weight in self._adj_list.get(node_id, []):
                if target_id not in visited:
                    visited.add(target_id)
                    target = self.nodes[target_id]
                    result.append(
                        {
                            "id": target_id,
                            "label": target.label,
                            "type": target.type,
                            "relation": relation,
                            "distance": depth + 1,
                        }
                    )
                    current.append((target_id, depth + 1))

        return result

    def query(self, question: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Query the knowledge graph with semantic + structural search.
        """
        logger.info(f"[GraphRAG] Querying: {question[:50]}...")

        # 1. Extract key terms
        terms = self._extract_terms(question)

        # 2. Find matching nodes
        matched_nodes = []
        for term in terms:
            node = self._find_node(term)
            if node:
                matched_nodes.append(node)

        # 3. Expand via graph traversal
        expanded = []
        for node in matched_nodes:
            neighbors = self.get_neighbors(node.label, max_hops=2)
            expanded.extend(neighbors)

        # 4. Get semantic context from memory (if available)
        semantic_context = ""
        if self.memory:
            try:
                semantic_context = self.memory.retrieve_context(question)
            except Exception:
                pass

        # 5. Combine results
        return {
            "query": question,
            "matched_nodes": [n.label for n in matched_nodes],
            "graph_context": expanded[:max_results],
            "semantic_context": semantic_context[:500] if semantic_context else "",
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
        }

    def _extract_terms(self, text: str) -> List[str]:
        """Extract key terms from text (simple tokenization)."""
        # Remove common words
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "what",
            "how",
            "why",
            "을",
            "를",
            "이",
            "가",
            "은",
            "는",
            "의",
            "에",
            "로",
        }

        words = text.lower().replace("?", "").replace(".", "").split()
        return [w for w in words if w not in stopwords and len(w) > 2]

    def build_from_text(self, text: str, source: str = "unknown") -> int:
        """
        Extract knowledge graph from text.
        Uses simple pattern matching (would use NER/RE in production).
        """
        # Simple triple extraction patterns
        patterns = [
            (r"(\w+)은\s+(\w+)이다", "is_a"),
            (r"(\w+)\s+has\s+(\w+)", "has"),
            (r"(\w+)\s+uses\s+(\w+)", "uses"),
            (r"(\w+)\s+기반", "based_on"),
        ]

        edges_added = 0

        # Add source as a node
        source_node = self.add_node(source, "document")

        # Extract entities (simplified)
        import re

        # Look for capitalized words as entities
        entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        for entity in set(entities):
            node = self.add_node(entity, "entity")
            self.add_edge(source, "mentions", entity)
            edges_added += 1

        # Look for Korean entities (simplified)
        kr_entities = re.findall(r"[가-힣]{2,}", text)
        for entity in set(kr_entities[:10]):  # Limit
            if len(entity) >= 3:
                self.add_node(entity, "concept")

        logger.info(
            f"🕸️ Built graph from text: {len(self.nodes)} nodes, {len(self.edges)} edges"
        )
        return edges_added

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "node_types": self._count_by_type(),
            "avg_degree": len(self.edges) * 2 / max(len(self.nodes), 1),
        }

    def _count_by_type(self) -> Dict[str, int]:
        counts = {}
        for node in self.nodes.values():
            counts[node.type] = counts.get(node.type, 0) + 1
        return counts

    def visualize_mermaid(self) -> str:
        """Generate Mermaid diagram of the graph."""
        lines = ["```mermaid", "graph LR"]

        # Add edges
        for edge in self.edges[:20]:  # Limit for readability
            source = self.nodes.get(edge.source_id)
            target = self.nodes.get(edge.target_id)
            if source and target:
                s_label = source.label[:15].replace(" ", "_")
                t_label = target.label[:15].replace(" ", "_")
                lines.append(f"    {s_label} -->|{edge.relation}| {t_label}")

        lines.append("```")
        return "\n".join(lines)


def get_graph_rag() -> GraphRAG:
    """Get a new GraphRAG instance."""
    return GraphRAG()
