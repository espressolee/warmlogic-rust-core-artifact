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
import threading
import time
import importlib.util
from unittest.mock import MagicMock

# Force path
sys.path.append(os.getcwd())

from warm_logic.kernel.evolution.evaluation_loop import EvaluationLoop  # noqa: E402
from warm_logic.kernel.evolution.idea_generator import IdeaGenerator  # noqa: E402
from warm_logic.kernel.intelligence.dht_reasoner import DHTReasoner  # noqa: E402
from warm_logic.kernel.intelligence.swarm_orchestrator import SwarmOrchestrator  # noqa: E402  # fmt: skip

# Imports for dependencies
from warm_logic.kernel.substrate.heartbeat import HeartbeatMonitor  # noqa: E402
from warm_logic.kernel.sys.hot_swapper import HotSwapManager as HotSwapper  # noqa: E402
from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence  # noqa: E402  # fmt: skip

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestAutonomy")


def test_autonomy_integration():
    print("Starting Phase 64: convergence Event Verification...")

    # 1. Mock Dependencies
    mock_mesh = MagicMock()
    mock_mesh.node_id = "node_Sovereign"
    mock_mesh.get_active_peers.return_value = ["node_Slave1", "node_Slave2"]

    # Heartbeat
    mock_hb = MagicMock(spec=HeartbeatMonitor)
    mock_hb.is_alive.return_value = True

    # Swarm
    orchestrator = SwarmOrchestrator(mock_mesh, bft_engine=MagicMock())

    # Reasoner
    mock_dht = MagicMock()
    mock_dht.node_id = "node_Sovereign"
    mock_dht.storage = {}

    # Mock put behavior to store within the mock object for retrieval
    def mock_put(k, v):
        mock_dht.storage[k] = v

    mock_dht.put.side_effect = mock_put
    reasoner = DHTReasoner(mock_dht)

    # Evolution
    swapper = HotSwapper()
    generator = IdeaGenerator(use_mock=True)
    evaluator = EvaluationLoop(generator, swapper)

    # 2. Initialize Sovereign Intelligence
    sov = SovereignIntelligence(
        node_id="node_Sovereign",
        heartbeat=mock_hb,
        orchestrator=orchestrator,
        reasoner=reasoner,
        evoluter=evaluator,
    )

    # 3. Verify convergence Trigger
    assert not sov.autonomy_event.triggered

    # Run loop in a thread to simulate daemon
    t = threading.Thread(target=sov.start_eternal_run)
    t.daemon = True
    t.start()

    module_name = "autonomy_test_code"
    module_path = os.path.abspath(f"{module_name}.py")
    candidate_path = os.path.abspath(f"{module_name}_candidate.py")

    try:
        time.sleep(1)  # Let it spin up

        print("\n[Phase 64.1] convergence Triggered")
        assert sov.autonomy_event.triggered

        # 4. Inject Stimuli (System Autonomy Check)

        # A. Goal Decomposition
        print("\n[Phase 64.2] Injecting Goal: 'Construct large-scale structure'")
        plan_id = sov.process_goal("Construct large-scale structure")
        tasks = orchestrator.active_plans[plan_id]
        assert len(tasks) > 0
        print(f"   -> Decomposed into {len(tasks)} tasks.")

        # B. Distributed Reasoning
        print("\n[Phase 64.3] Injecting Insight Topic: 'Energy Efficiency'")
        verdict = sov.synthesize_thought("Energy Efficiency")
        assert "node_Sovereign" in verdict
        print(f"   -> Verdict: {verdict}")

        # C. Self-Evolution Setup (Slow Func)
        print("\n[Phase 64.4] Testing Evolution Trigger")
        with open(module_path, "w", encoding="utf-8") as f:
            f.write("""
def slow_fib(n):
    if n <= 1: return n
    return slow_fib(n-1) + slow_fib(n-2)
""")

        # Ensure module is registered so EvaluationLoop can resolve sys.modules[module_name].
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Trigger evolution via Sovereign
        success = sov.process_optimization(module_name, "slow_fib")
        assert success
        print("   -> Evolution successful.")

        print("\n[Phase 64] full autonomy Event Verified.")
    finally:
        sov.stop()
        t.join(timeout=2)
        sys.modules.pop(module_name, None)
        sys.modules.pop(f"{module_name}_candidate", None)
        if os.path.exists(module_path):
            os.remove(module_path)
        if os.path.exists(candidate_path):
            os.remove(candidate_path)


if __name__ == "__main__":
    test_autonomy_integration()
