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
import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    import networkx as nx
except ImportError:
    # Minimal directed graph stub for environments without networkx

    class _StubDiGraph:
        """Pure-Python directed graph matching the networkx API subset used here."""

        def __init__(self) -> None:
            self._nodes: Dict[str, Dict[str, Any]] = {}  # name -> metadata
            self._edges: Dict[tuple, Dict[str, Any]] = {}  # (src, tgt) -> metadata

        # --- Node API ---
        def add_node(self, name: str, **kwargs: Any) -> None:
            self._nodes[name] = kwargs

        def has_node(self, name: str) -> bool:
            return name in self._nodes

        @property
        def nodes(self) -> Dict[str, Dict[str, Any]]:
            return self._nodes

        def number_of_nodes(self) -> int:
            return len(self._nodes)

        # --- Edge API ---
        def add_edge(self, src: str, tgt: str, **kwargs: Any) -> None:
            if src not in self._nodes:
                self._nodes[src] = {}
            if tgt not in self._nodes:
                self._nodes[tgt] = {}
            self._edges[(src, tgt)] = kwargs

        def number_of_edges(self) -> int:
            return len(self._edges)

        def has_edge(self, src: str, tgt: str) -> bool:
            return (src, tgt) in self._edges

        def neighbors(self, node: str) -> List[str]:
            return [tgt for (src, tgt) in self._edges if src == node]

        def clear(self) -> None:
            self._nodes.clear()
            self._edges.clear()

    class _NetworkXNoPath(Exception):
        pass

    class _NodeNotFound(Exception):
        pass

    class _MockNX:
        DiGraph = _StubDiGraph
        NetworkXNoPath = _NetworkXNoPath
        NodeNotFound = _NodeNotFound

        @staticmethod
        def node_link_data(graph: "_StubDiGraph") -> Dict[str, Any]:
            return {
                "nodes": [{"id": n, **m} for n, m in graph._nodes.items()],
                "links": [
                    {"source": s, "target": t, **m}
                    for (s, t), m in graph._edges.items()
                ],
            }

        @staticmethod
        def node_link_graph(data: Dict[str, Any]) -> "_StubDiGraph":
            g = _StubDiGraph()
            for node in data.get("nodes", []):
                nid = node.pop("id", None)
                if nid is not None:
                    g.add_node(nid, **node)
            for link in data.get("links", []):
                s = link.pop("source", None)
                t = link.pop("target", None)
                if s is not None and t is not None:
                    g.add_edge(s, t, **link)
            return g

        @staticmethod
        def shortest_path(
            graph: "_StubDiGraph",
            source: Optional[str] = None,
            target: Optional[str] = None,
        ) -> List[str]:
            # BFS
            if source not in graph._nodes:
                raise _NodeNotFound(source)
            if target not in graph._nodes:
                raise _NodeNotFound(target)
            visited = {source: [source]}
            queue = [source]
            while queue:
                node = queue.pop(0)
                for neighbor in graph.neighbors(node):
                    if neighbor not in visited:
                        visited[neighbor] = visited[node] + [neighbor]
                        if neighbor == target:
                            return visited[neighbor]
                        queue.append(neighbor)
            raise _NetworkXNoPath(f"No path between {source} and {target}")

    nx = _MockNX()

logger = logging.getLogger("GraphVault")


class GraphVault:
    """
    [Phase 68] Knowledge Graph Memory.
    Models relationships between concepts using NetworkX.
    Persists as a node-link JSON structure.
    """

    def __init__(self, persist_path: str = "data/memory/sovereign_graph.json"):
        self.persist_path = persist_path
        self.graph = nx.DiGraph()

        # Ensure directory
        os.makedirs(os.path.dirname(persist_path), exist_ok=True)

        self.load()

    def load(self) -> None:
        """Loads the graph from disk."""
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, "r") as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
                logger.info(
                    f"🕸️ [GraphVault] Loaded Knowledge Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges"
                )
            except Exception as e:
                logger.error(f"[GraphVault] Failed to load graph: {e}")
                self.graph = nx.DiGraph()  # Fallback
        else:
            logger.info("[GraphVault] Initialized new Knowledge Graph.")

    def save(self) -> None:
        """Persists the graph to disk."""
        try:
            data = nx.node_link_data(self.graph)
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("[GraphVault] Graph persisted.")
        except Exception as e:
            logger.error(f"[GraphVault] Failed to save graph: {e}")

    def add_concept(
        self,
        name: str,
        type: str = "Concept",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Adds a node to the graph."""
        if metadata is None:
            metadata = {}
        metadata["type"] = type
        self.graph.add_node(name, **metadata)
        self.save()

    def link_concepts(
        self, source: str, target: str, relation: str, weight: float = 1.0
    ) -> None:
        """Adds a directed edge between concepts."""
        # Ensure nodes exist
        if not self.graph.has_node(source):
            self.add_concept(source)
        if not self.graph.has_node(target):
            self.add_concept(target)

        self.graph.add_edge(source, target, relation=relation, weight=weight)
        logger.debug(f"[Graph] Linked '{source}' --{relation}--> '{target}'")
        self.save()

    def find_path(self, start: str, end: str) -> List[str]:
        """Finds the shortest path between two concepts."""
        try:
            return list(nx.shortest_path(self.graph, source=start, target=end))
        except nx.NetworkXNoPath:
            return []
        except nx.NodeNotFound:
            return []

    def get_related(self, concept: str) -> List[str]:
        """Returns direct neighbors."""
        if self.graph.has_node(concept):
            return list(self.graph.neighbors(concept))
        return []

    def wipe(self) -> None:
        self.graph.clear()
        self.save()
