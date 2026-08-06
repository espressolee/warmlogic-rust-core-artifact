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
import sys

# Force path
sys.path.append(os.getcwd())

from warm_logic.kernel.evolution.mcts_planner import MCTSNode, MCTSPlanner

logging.basicConfig(level=logging.INFO)


def test_mcts_logic():
    print("Starting MCTS Planner Verification...")

    # 1. Define specific search space
    # Goal: Find the "Optimized" string.
    # We mock the evaluator to return higher score for strings closer to "Optimized"

    def mock_evaluator(code: str) -> float:
        if code == "Optimized":
            return 100.0
        if code == "Better":
            return 50.0
        if code == "Initial":
            return 10.0
        return 0.0

    planner = MCTSPlanner(mock_evaluator)

    # 2. Mock Expansion (Inject Children manually for test)
    # In real system, this would be LLM generating variations.
    root = MCTSNode("Initial")

    child_bad = MCTSNode("Bad", parent=root)
    child_better = MCTSNode("Better", parent=root)

    # Grandchild
    child_optimized = MCTSNode("Optimized", parent=child_better)
    child_better.children.append(child_optimized)

    root.children = [child_bad, child_better]

    # 3. Inject into planner (bypass normal search for unit test of selection/backprop)
    # We will manually run steps to verify UCT and Backprop

    print("   -> Testing Selection/Backpropagation...")

    # Simulate visiting "Better"
    score = planner._simulate(child_better)  # 50.0
    planner._backpropagate(child_better, score)

    assert root.visits == 1
    assert root.score == 50.0
    assert child_better.visits == 1
    assert child_better.score == 50.0

    # Simulate visiting "Bad"
    score = planner._simulate(child_bad)  # 0.0
    planner._backpropagate(child_bad, score)

    assert root.visits == 2
    assert root.score == 50.0
    assert child_bad.visits == 1
    assert child_bad.score == 0.0

    # Now check Selection (UCT)
    # exploration_weight=1.41
    # UCT(Better) = 50/1 + 1.41*sqrt(log(2)/1) = 50 + 1.17 = 51.17
    # UCT(Bad) = 0/1 + 1.41*sqrt(log(2)/1) = 1.17

    selected = planner._select(root)
    # Since children are visited, it should pick based on UCT.
    # However, _select checks for unvisited children first.
    # But here both are visited.
    # Wait, grandchild is unvisited.
    # Does select descend?
    # Logic: while node.children: -> if any unvisited child, return it. else max UCT.

    # Better has unvisited child (Optimized).
    # Bad has no children.

    # If we pick "Better" (Score 51), we descend to "Better".
    # Inside "Better", it has "Optimized" (visits=0). It should return "Optimized".

    assert selected.code == "Optimized"
    print("   -> UCT Selection correct (Found 'Optimized' node).")

    print("[Phase 65.2] MCTS Logic Verified!")


if __name__ == "__main__":
    test_mcts_logic()
