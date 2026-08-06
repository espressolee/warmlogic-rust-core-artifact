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
# The connective-word list is intentionally bilingual; the Korean entries are matched
# against thought text to score structured reasoning. Do not translate.

"""
[Phase 101.1] Tree-of-Thought Reasoning Engine.
Implements branching thought paths with evaluation and backtracking.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("TreeOfThought")


@dataclass
class ThoughtNode:
    """A single node in the thought tree."""

    id: str
    content: str
    score: float = 0.0
    children: List["ThoughtNode"] = field(default_factory=list)
    parent_id: Optional[str] = None
    depth: int = 0

    def add_child(self, content: str) -> "ThoughtNode":
        child = ThoughtNode(
            id=f"{self.id}.{len(self.children)}",
            content=content,
            parent_id=self.id,
            depth=self.depth + 1,
        )
        self.children.append(child)
        return child


class TreeOfThoughtEngine:
    """
    [Phase 101.1] Tree-of-Thought Reasoner.

    Implements branching reasoning with:
    1. Multiple thought paths (branching)
    2. Evaluation of each path (scoring)
    3. Pruning of low-quality paths
    4. Selection of best path
    """

    def __init__(
        self, llm: Optional[Any] = None, max_depth: int = 3, branch_factor: int = 3
    ) -> None:
        self.llm = llm
        self.max_depth = max_depth
        self.branch_factor = branch_factor
        self.thought_tree: Optional[ThoughtNode] = None
        self._node_counter = 0
        logger.info("[TreeOfThought] Engine Initialized.")

    def _generate_id(self) -> str:
        self._node_counter += 1
        return f"N{self._node_counter:04d}"

    def _score_thought(self, thought: str, goal: str) -> float:
        """Score a thought's relevance to the goal (0.0 to 1.0)."""
        # Simple heuristic scoring (would use LLM in production)
        score = 0.5

        # Keyword matching
        goal_words = set(goal.lower().split())
        thought_words = set(thought.lower().split())
        overlap = len(goal_words & thought_words)
        score += overlap * 0.1

        # Length penalty (too short or too long)
        if len(thought) < 20:
            score -= 0.2
        elif len(thought) > 500:
            score -= 0.1

        # Bonus for structured thinking
        if any(
            kw in thought.lower()
            for kw in ["because", "therefore", "thus", "따라서", "그러므로"]
        ):
            score += 0.15

        return min(max(score, 0.0), 1.0)

    def _generate_branches(self, node: ThoughtNode, goal: str) -> List[ThoughtNode]:
        """Generate child thoughts from a parent node."""
        branches = []

        if self.llm:
            # Use LLM to generate branches (production mode)
            prompt = f"""Given the goal: {goal}
And the current thought: {node.content}

Generate {self.branch_factor} different next steps or continuations.
Each should be a distinct approach."""

            try:
                response = self.llm.generate(prompt)
                # Parse response into branches (simplified)
                lines = [l.strip() for l in response.split("\n") if l.strip()]
                for line in lines[: self.branch_factor]:
                    child = node.add_child(line)
                    child.score = self._score_thought(line, goal)
                    branches.append(child)
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}")

        # Fallback: Generate template branches
        if not branches:
            templates = [
                f"Approach 1: Analyze {goal} by breaking it into components",
                f"Approach 2: Consider {goal} from a different perspective",
                f"Approach 3: Evaluate the constraints and requirements of {goal}",
            ]
            for i, template in enumerate(templates[: self.branch_factor]):
                child = node.add_child(template)
                child.score = self._score_thought(template, goal)
                branches.append(child)

        return branches

    def _prune_tree(
        self, nodes: List[ThoughtNode], keep_top: int = 2
    ) -> List[ThoughtNode]:
        """Prune low-scoring branches, keeping only top performers."""
        sorted_nodes = sorted(nodes, key=lambda n: n.score, reverse=True)
        return sorted_nodes[:keep_top]

    def think(self, goal: str, initial_thought: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute Tree-of-Thought reasoning.

        Returns the best path through the thought tree.
        """
        logger.info(f"[ToT] Starting for goal: {goal[:50]}...")

        # Initialize root
        root_content = initial_thought or f"Goal: {goal}"
        self.thought_tree = ThoughtNode(id=self._generate_id(), content=root_content)
        self.thought_tree.score = self._score_thought(root_content, goal)

        # Breadth-first tree expansion with pruning
        current_level = [self.thought_tree]
        all_paths = []

        for depth in range(self.max_depth):
            next_level = []

            for node in current_level:
                # Generate branches
                branches = self._generate_branches(node, goal)
                next_level.extend(branches)

            if not next_level:
                break

            # Prune to keep only best branches
            current_level = self._prune_tree(next_level, keep_top=2)
            all_paths.extend(current_level)

        # Find best path
        best_node = (
            max(all_paths, key=lambda n: n.score) if all_paths else self.thought_tree
        )

        # Reconstruct path
        path: List[Dict[str, Any]] = []
        current_node: Optional[ThoughtNode] = best_node
        while current_node:
            path.append(
                {
                    "id": current_node.id,
                    "content": current_node.content,
                    "score": current_node.score,
                }
            )
            # Find parent (simplified - would use proper tree traversal)
            current_node = None  # In full impl, traverse back via parent_id

        path.reverse()

        result = {
            "goal": goal,
            "best_thought": best_node.content,
            "best_score": best_node.score,
            "depth_reached": best_node.depth,
            "total_nodes_explored": self._node_counter,
            "path": path,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"[ToT] Complete. Best score: {best_node.score:.2f}")
        return result

    def get_tree_summary(self) -> str:
        """Get a visual summary of the thought tree."""
        if not self.thought_tree:
            return "No tree generated yet."

        lines = ["# Thought Tree Summary\n"]

        def traverse(node: ThoughtNode, prefix: str = "") -> None:
            lines.append(f"{prefix}[{node.score:.2f}] {node.content[:60]}...")
            for child in node.children:
                traverse(child, prefix + "  ")

        traverse(self.thought_tree)
        return "\n".join(lines)


def tree_of_thought(goal: str, llm: Optional[Any] = None) -> Dict[str, Any]:
    """Convenience function for Tree-of-Thought reasoning."""
    engine = TreeOfThoughtEngine(llm=llm)
    return engine.think(goal)
