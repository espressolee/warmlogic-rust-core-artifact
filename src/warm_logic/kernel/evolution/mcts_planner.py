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
import math
from typing import Callable, List, Optional

# MCTS Planner for Code Refinement
# "Thought Trees"

logger = logging.getLogger("MCTSPlanner")


class MCTSNode:
    def __init__(self, code: str, parent: Optional["MCTSNode"] = None) -> None:
        self.code = code
        self.parent = parent
        self.children: List["MCTSNode"] = []
        self.visits = 0
        self.score = 0.0

    def uct_value(self, exploration_weight: float = 1.41) -> float:
        if self.visits == 0:
            return float("inf")
        parent_visits = self.parent.visits if self.parent else 1
        return (self.score / self.visits) + exploration_weight * math.sqrt(
            math.log(parent_visits) / self.visits
        )


class MCTSPlanner:
    """
    Experimental Planner.
    Uses MCTS to explore chains of code modifications (Refinements).
    """

    def __init__(self, evaluator_callback: Callable[[str], float]) -> None:
        self.evaluator = evaluator_callback

    def search(self, initial_code: str, iterations: int = 10) -> str:
        root = MCTSNode(initial_code)

        for i in range(iterations):
            node = self._select(root)
            # Expansion would involve querying LLM for "Variations" of this code
            # For Phase 65.1, we leave expansion as a stub or simulated step
            # self._expand(node)
            score = self._simulate(node)
            self._backpropagate(node, score)

        # Select best child
        if not root.children:
            return root.code

        return max(root.children, key=lambda n: n.visits).code

    def _select(self, node: MCTSNode) -> MCTSNode:
        while node.children:
            if any(n.visits == 0 for n in node.children):
                return next(n for n in node.children if n.visits == 0)
            node = max(node.children, key=lambda n: n.uct_value())
        return node

    def _simulate(self, node: MCTSNode) -> float:
        # Call the EvaluationLoop's benchmark function
        return float(self.evaluator(node.code))

    def _backpropagate(self, node: Optional[MCTSNode], score: float) -> None:
        while node:
            node.visits += 1
            node.score += score
            node = node.parent
