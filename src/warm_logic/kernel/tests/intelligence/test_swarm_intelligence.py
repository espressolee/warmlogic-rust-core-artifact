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
from unittest.mock import MagicMock

# Force path
sys.path.append(os.getcwd())

from warm_logic.kernel.intelligence.dht_reasoner import DHTReasoner
from warm_logic.kernel.intelligence.swarm_orchestrator import SwarmOrchestrator
from warm_logic.kernel.ops.governance import QuadraticGovernanceEngine, SwarmArbiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSwarmIntelligence")


def test_swarm_workflow():
    print("Starting Advanced Swarm Intelligence Verification...")

    # --- 1. Swarm Orchestration ---
    print("\nTesting Swarm Orchestration...")
    mesh_mock = MagicMock()
    mesh_mock.node_id = "node_A"
    mesh_mock.get_active_peers.return_value = ["node_B", "node_C"]
    mesh_mock.routing.get_all_contacts.return_value = []

    orchestrator = SwarmOrchestrator(mesh_mock, bft_engine=MagicMock())

    goal = "Analyze System Health completely"
    plan_id = orchestrator.submit_goal(goal)

    assert plan_id in orchestrator.active_plans
    tasks = orchestrator.active_plans[plan_id]
    assert len(tasks) == 3  # Heuristic splits into 3 subtasks

    assignments = [t.assigned_node for t in tasks]
    print(f"Task Assignments: {assignments}")
    assert all(node == "node_A" for node in assignments)
    print("Swarm Orchestration Verified.")

    # --- 2. Distributed Reasoning ---
    print("\nTesting Distributed Reasoning...")
    dht_mock = MagicMock()
    dht_mock.node_id = "node_A"
    storage = {}

    # Mock DHT behavior
    def mock_put(k, v):
        storage[k] = v

    dht_mock.put.side_effect = mock_put
    dht_mock.storage = storage  # For our gather_insights logic to read backward

    reasoner_a = DHTReasoner(dht_mock)

    # Node A publishes thought
    reasoner_a.publish_insight("security_audit", "Node A found vulnerability X")

    # Simulate Node B publishing thought (writes to same shared storage mock)
    key_b = "insight:security_audit:node_B"
    storage[key_b] = "Node B confirms vulnerability X is critical"

    # Synthesis
    verdict = reasoner_a.synthesize_verdict("security_audit")
    print(f"Collective Verdict: {verdict}")
    assert "Node A found" in verdict
    assert "Node B confirms" in verdict
    print("Distributed Reasoning Verified.")

    # --- 3. Swarm Ethics Arbiter ---
    print("\n Testing Swarm Ethics Arbiter...")
    token_manager = MagicMock()
    token_manager.get_balance.return_value = 100.0

    gov = QuadraticGovernanceEngine(token_manager)
    arbiter = SwarmArbiter(gov)

    # Submit conflicting proposals
    prop_destroy = gov.submit_proposal(
        "node_A", "DELETE_ARCHIVES", {"value": "all"}, duration=100
    )
    prop_save = gov.submit_proposal(
        "node_B", "ARCHIVE_DATA", {"value": "all"}, duration=100
    )

    # Simulate votes
    gov.cast_vote("node_A", prop_destroy, support=True)  # Power 10
    gov.cast_vote("node_B", prop_save, support=True)  # Power 10

    # Arbitrate
    winner_id = arbiter.resolve_conflict(prop_destroy, prop_save)
    winner_prop = gov.proposals[winner_id]

    print(f"Arbiter chose: {winner_prop.action}")

    # Expect ARCHIVE (preservation) to win over DELETE (destruction) despite equal votes
    # Score Save: +10 (keyword) + 10 (vote) = 20
    # Score Destroy: -5 (keyword) + 10 (vote) = 5
    assert winner_id == prop_save
    print("Swarm Ethics Arbiter Verified.")

    print("\nPhase 62 Verification Successful!")


if __name__ == "__main__":
    try:
        test_swarm_workflow()
    except Exception as e:
        print(f"Verification Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
