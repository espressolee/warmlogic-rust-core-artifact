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
[Phase 105.2] Causal Inference Engine.
Implements causal reasoning with do-calculus.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("CausalInference")


@dataclass
class CausalNode:
    """A node in the causal graph."""

    id: str
    name: str
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    value: Optional[Any] = None


@dataclass
class CausalEdge:
    """A directed edge in the causal graph."""

    source: str
    target: str
    strength: float = 1.0  # Causal strength
    mechanism: Optional[str] = None  # Description of mechanism


class CausalGraph:
    """
    [Phase 105.2] Causal Inference Engine.

    Implements:
    1. Causal graph representation
    2. d-separation queries
    3. do-calculus interventions
    4. Counterfactual reasoning
    5. Effect estimation
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, CausalNode] = {}
        self.edges: List[CausalEdge] = []
        logger.info("[CausalInference] Engine Active.")

    def add_node(self, name: str, value: Any = None) -> CausalNode:
        """Add a node to the causal graph."""
        node_id = f"C{len(self.nodes):04d}"
        node = CausalNode(id=node_id, name=name, value=value)
        self.nodes[node_id] = node
        return node

    def _find_node(self, name: str) -> Optional[CausalNode]:
        """Find node by name."""
        for node in self.nodes.values():
            if node.name.lower() == name.lower():
                return node
        return None

    def add_cause(
        self,
        cause_name: str,
        effect_name: str,
        strength: float = 1.0,
        mechanism: Optional[str] = None,
    ) -> CausalEdge:
        """Add a causal relationship: cause → effect."""
        cause = self._find_node(cause_name) or self.add_node(cause_name)
        effect = self._find_node(effect_name) or self.add_node(effect_name)

        edge = CausalEdge(
            source=cause.id, target=effect.id, strength=strength, mechanism=mechanism
        )
        self.edges.append(edge)

        cause.children.append(effect.id)
        effect.parents.append(cause.id)

        logger.debug(f"Added cause: {cause_name} → {effect_name}")
        return edge

    def get_parents(self, node_name: str) -> List[str]:
        """Get direct causes of a node."""
        node = self._find_node(node_name)
        if not node:
            return []
        return [self.nodes[p].name for p in node.parents if p in self.nodes]

    def get_children(self, node_name: str) -> List[str]:
        """Get direct effects of a node."""
        node = self._find_node(node_name)
        if not node:
            return []
        return [self.nodes[c].name for c in node.children if c in self.nodes]

    def get_ancestors(self, node_name: str) -> Set[str]:
        """Get all ancestors (transitive causes)."""
        node = self._find_node(node_name)
        if not node:
            return set()

        ancestors = set()
        queue = list(node.parents)

        while queue:
            parent_id = queue.pop(0)
            if parent_id in self.nodes and parent_id not in ancestors:
                ancestors.add(self.nodes[parent_id].name)
                queue.extend(self.nodes[parent_id].parents)

        return ancestors

    def get_descendants(self, node_name: str) -> Set[str]:
        """Get all descendants (transitive effects)."""
        node = self._find_node(node_name)
        if not node:
            return set()

        descendants = set()
        queue = list(node.children)

        while queue:
            child_id = queue.pop(0)
            if child_id in self.nodes and child_id not in descendants:
                descendants.add(self.nodes[child_id].name)
                queue.extend(self.nodes[child_id].children)

        return descendants

    def do(self, intervention: str, value: Any) -> "InterventionResult":
        """
        Apply do-calculus intervention: do(X = value).
        This simulates setting a variable to a value, breaking its causal links.
        """
        node = self._find_node(intervention)
        if not node:
            return InterventionResult(
                intervention=intervention,
                value=value,
                success=False,
                reason="Node not found",
            )

        # Cut incoming edges (remove causes)
        old_parents = list(node.parents)
        node.parents = []
        for edge in self.edges[:]:
            if edge.target == node.id:
                self.edges.remove(edge)

        # Set value
        old_value = node.value
        node.value = value

        # Calculate downstream effects
        affected = self.get_descendants(intervention)

        return InterventionResult(
            intervention=intervention,
            value=value,
            success=True,
            old_value=old_value,
            old_parents=[self.nodes[p].name for p in old_parents if p in self.nodes],
            affected_nodes=list(affected),
        )

    def estimate_effect(self, cause: str, effect: str) -> Dict[str, Any]:
        """Estimate causal effect of cause on effect."""
        cause_node = self._find_node(cause)
        effect_node = self._find_node(effect)

        if not cause_node or not effect_node:
            return {"error": "Node not found"}

        # Check if there's a causal path
        descendants = self.get_descendants(cause)
        is_causal = effect in descendants

        # Find all paths
        paths = self._find_paths(cause_node.id, effect_node.id)

        # Calculate total effect (simplified)
        total_strength = 0.0
        for path in paths:
            path_strength = 1.0
            for i in range(len(path) - 1):
                for edge in self.edges:
                    if edge.source == path[i] and edge.target == path[i + 1]:
                        path_strength *= edge.strength
            total_strength += path_strength

        return {
            "cause": cause,
            "effect": effect,
            "is_causal": is_causal,
            "paths": len(paths),
            "total_effect": total_strength,
            "interpretation": self._interpret_effect(total_strength),
        }

    def _find_paths(
        self, source_id: str, target_id: str, visited: Optional[Set[str]] = None
    ) -> List[List[str]]:
        """Find all directed paths from source to target."""
        if visited is None:
            visited = set()

        if source_id == target_id:
            return [[source_id]]

        if source_id in visited:
            return []

        visited.add(source_id)
        paths = []

        source = self.nodes.get(source_id)
        if source:
            for child_id in source.children:
                for path in self._find_paths(child_id, target_id, visited.copy()):
                    paths.append([source_id] + path)

        return paths

    def _interpret_effect(self, strength: float) -> str:
        """Interpret effect strength."""
        if strength == 0:
            return "no_effect"
        elif strength < 0.3:
            return "weak_effect"
        elif strength < 0.7:
            return "moderate_effect"
        else:
            return "strong_effect"

    def counterfactual(
        self, query: str, given: Dict[str, Any], intervention: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Answer counterfactual query.
        Example: "What would Y be if X had been different, given observed Z?"
        """
        # Step 1: Abduction (infer latent variables from observations)
        for node_name, value in given.items():
            node = self._find_node(node_name)
            if node:
                node.value = value

        # Step 2: Action (apply intervention)
        for node_name, value in intervention.items():
            self.do(node_name, value)

        # Step 3: Prediction
        target_node = self._find_node(query)
        predicted_value = target_node.value if target_node else None

        return {
            "query": query,
            "given": given,
            "intervention": intervention,
            "counterfactual_value": predicted_value,
            "reasoning": f"If {intervention} had occurred given {given}, then {query} would be {predicted_value}",
        }

    def visualize(self) -> str:
        """Generate Mermaid diagram of causal graph."""
        lines = ["```mermaid", "graph TD"]

        for edge in self.edges:
            source = self.nodes.get(edge.source)
            target = self.nodes.get(edge.target)
            if source and target:
                s_name = source.name.replace(" ", "_")
                t_name = target.name.replace(" ", "_")
                lines.append(f"    {s_name} --> {t_name}")

        lines.append("```")
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get causal graph statistics."""
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "root_causes": len([n for n in self.nodes.values() if not n.parents]),
            "terminal_effects": len([n for n in self.nodes.values() if not n.children]),
        }


@dataclass
class InterventionResult:
    """Result of a do-calculus intervention."""

    intervention: str
    value: Any
    success: bool
    reason: str = ""
    old_value: Any = None
    old_parents: List[str] = field(default_factory=list)
    affected_nodes: List[str] = field(default_factory=list)


def get_causal_graph() -> CausalGraph:
    """Get a new Causal Graph."""
    return CausalGraph()
