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
import importlib
from unittest.mock import MagicMock

from unittest.mock import patch

import pytest


@pytest.fixture
def mock_deps():
    return {
        "heartbeat": MagicMock(),
        "orchestrator": MagicMock(),
        "reasoner": MagicMock(),
        "evoluter": MagicMock(),
        "blackbox": MagicMock(),
        "memory": MagicMock(),
        "graph": MagicMock(),
        "telemetry": MagicMock(),
    }


@pytest.fixture
def sovereign(mock_deps):
    module = importlib.import_module("warm_logic.kernel.sys.sovereign_intelligence")
    with (
        patch.object(module, "VectorVault") as MockVector,
        patch.object(module, "GraphVault") as MockGraph,
        patch.object(module, "BlackBox") as MockAudit,
        patch.object(module, "tracer"),
    ):
        pv = MockVector.return_value
        gv = MockGraph.return_value
        bb = MockAudit.return_value

        si = module.SovereignIntelligence(
            node_id="test-node-001",
            heartbeat=mock_deps["heartbeat"],
            orchestrator=mock_deps["orchestrator"],
            reasoner=mock_deps["reasoner"],
            evoluter=mock_deps["evoluter"],
        )
        # Verify wiring
        assert si.memory == pv
        assert si.graph == gv
        assert si.audit_log == bb

        # Adjust loop delay for speed
        si._loop_delay = 0.001

        yield si


def test_sovereign_init(sovereign):
    """Test verification of initialization."""
    assert sovereign.node_id == "test-node-001"
    assert sovereign.running is False


def test_start_eternal_run_loop(sovereign):
    """Test start_eternal_run loop execution."""
    # We need to break the infinite loop.
    # Approach: Let it run once, then throw an exception or set running=False via side effect

    # Mock _tick to stop the loop after one call
    def stop_loop():
        sovereign.running = False

    with patch.object(sovereign, "_tick", side_effect=stop_loop) as mock_tick:
        sovereign.start_eternal_run()

    assert mock_tick.called
    assert (
        sovereign.autonomy_event.triggered is True
    )  # Checked AutonomyEvent source, uses .triggered boolean
    # Note: AutonomyEvent implementation details might vary, assuming trigger() works.

    sovereign.audit_log.log.assert_called()  # Check awakening log


def test_start_eternal_run_interrupt(sovereign):
    """Test KeyboardInterrupt handling."""
    with patch.object(sovereign, "_tick", side_effect=KeyboardInterrupt):
        sovereign.start_eternal_run()
    # Should exit gracefully
    assert (
        sovereign.running is True
    )  # Loop sets running=True; interrupt breaks the loop without resetting it
    # The code:
    # try: while self.running: ... except KeyboardInterrupt: logger.info...
    # It catches but doesn't set self.running = False. So it stays True.


def test_start_eternal_run_error(sovereign):
    """Test critical failure handling."""
    with patch.object(sovereign, "_tick", side_effect=Exception("Boom")):
        sovereign.start_eternal_run()

    assert sovereign.running is False  # Exception handler sets self.running = False


def test_tick_heartbeat_alive(sovereign):
    """Test tick when heartbeat is fine."""
    sovereign.heartbeat.is_alive.return_value = True
    sovereign._tick()
    assert not sovereign.heartbeat.start.called


def test_tick_heartbeat_dead(sovereign):
    """Test tick when heartbeat needs resuscitation."""
    sovereign.heartbeat.is_alive.return_value = False
    sovereign._tick()
    assert sovereign.heartbeat.start.called
    sovereign.audit_log.log.assert_called_with(
        {"action": "heartbeat_restart", "reason": "unstable"}
    )


def test_process_goal_no_memory(sovereign):
    """Test process_goal without prior memory recall."""
    sovereign.memory.query_thoughts.return_value = []
    sovereign.orchestrator.submit_goal.return_value = "plan-123"

    pid = sovereign.process_goal("Build a starship")

    assert pid == "plan-123"
    sovereign.memory.store_plan.assert_called_with(
        "Build a starship", ["Dispatched to Swarm"], "In Progress"
    )
    sovereign.audit_log.log.assert_called()


def test_process_goal_with_memory(sovereign):
    """Test process_goal with memory recall."""
    sovereign.memory.query_thoughts.return_value = ["Previous starship plan"]

    sovereign.process_goal("Build a starship")

    # Should verify log indicates recall
    # We can check the audit log call arg
    args, _ = sovereign.audit_log.log.call_args
    assert args[0]["recalled"] is True


def test_process_optimization(sovereign):
    """Test process_optimization success path."""
    sovereign.evoluter.evaluate_and_evolve.return_value = True

    res = sovereign.process_optimization("module_a", "func_b")
    assert res is True

    sovereign.graph.add_concept.assert_any_call("module_a", type="Module")
    sovereign.graph.link_concepts.assert_any_call("module_a", "func_b", "CONTAINS")


def test_process_optimization_failure(sovereign):
    """Test process_optimization failure path."""
    sovereign.evoluter.evaluate_and_evolve.return_value = False

    res = sovereign.process_optimization("module_a", "func_b")
    assert res is False

    assert not sovereign.graph.add_concept.called


def test_synthesize_thought(sovereign):
    """Test synthesize_thought flow."""
    sovereign.reasoner.synthesize_verdict.return_value = "It is 42"

    verdict = sovereign.synthesize_thought("Meaning of Life")
    assert verdict == "It is 42"

    sovereign.reasoner.publish_insight.assert_called()
    sovereign.memory.store_thought.assert_called()
    sovereign.audit_log.log.assert_called()


def test_stop(sovereign):
    """Test stop method."""
    sovereign.running = True
    sovereign.stop()
    assert sovereign.running is False
    sovereign.audit_log.log.assert_called_with(
        {"action": "shutdown", "reason": "command"}
    )
