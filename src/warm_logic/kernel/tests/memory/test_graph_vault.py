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

from warm_logic.kernel.memory.graph_vault import GraphVault

logging.basicConfig(level=logging.INFO)


def test_graph_knowledge():
    print("Starting Phase 68: Knowledge Graph Verification...")

    # 0. Clean Setup
    test_graph_path = "data/memory/test_graph.json"
    if os.path.exists(test_graph_path):
        os.remove(test_graph_path)

    # 1. Initialize Graph
    print("   -> [Session 1] Initializing Graph Vault...")
    graph = GraphVault(persist_path=test_graph_path)

    # 2. Build Knowledge Structure
    print("   -> [Session 1] Building Concept Map...")
    graph.add_concept("Kernel", type="Module")
    graph.add_concept("Optimization", type="Goal")
    graph.add_concept("Sovereignty", type="Goal")

    graph.link_concepts("Kernel", "Sovereignty", "ENABLES")
    graph.link_concepts("Optimization", "Kernel", "IMPROVES")

    # 3. Verify Basic Relationships
    print(
        f"   -> [Graph] Nodes: {graph.graph.number_of_nodes()}, Edges: {graph.graph.number_of_edges()}"
    )
    assert graph.graph.has_edge("Optimization", "Kernel")

    # 4. Simulate Restart
    del graph
    print("   -> [System Restart] Re-loading Graph...")
    graph_v2 = GraphVault(persist_path=test_graph_path)

    # 5. Verify Persistence & Pathfinding
    print("   -> [Session 2] Finding path from 'Optimization' to 'Sovereignty'...")
    # Expected: Optimization -> Kernel -> Sovereignty
    path = graph_v2.find_path("Optimization", "Sovereignty")

    print(f"   -> Retrieved Path: {path}")

    assert path == ["Optimization", "Kernel", "Sovereignty"]

    print("\n[Phase 68] Knowledge Graph Verified!")
    print("   -> Concepts linked and traversed.")
    print("   -> Graph structure persisted.")

    # Cleanup
    if os.path.exists(test_graph_path):
        os.remove(test_graph_path)


if __name__ == "__main__":
    test_graph_knowledge()
