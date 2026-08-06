# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic Sovereign Intelligence."""

import importlib
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# Mark all tests in this module to run in same xdist group to avoid parallel conflicts
pytestmark = pytest.mark.xdist_group("sovereign_intelligence")

# Module name to isolate
_MODULE_NAME = "warm_logic.kernel.sys.sovereign_intelligence"


@pytest.fixture(autouse=True)
def isolate_module():
    """Remove module from cache before each test to ensure fresh import."""
    # Remove the module from sys.modules if it exists
    if _MODULE_NAME in sys.modules:
        del sys.modules[_MODULE_NAME]
    yield
    # Cleanup after test
    if _MODULE_NAME in sys.modules:
        del sys.modules[_MODULE_NAME]


# Mock all dependencies before importing
@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies."""
    with (
        patch(
            "warm_logic.kernel.events.autonomy_event.AutonomyEvent"
        ) as mock_autonomy_event,
        patch(
            "warm_logic.kernel.evolution.evaluation_loop.EvaluationLoop"
        ) as mock_eval,
        patch("warm_logic.kernel.evolution.idea_generator.IdeaGenerator") as mock_idea,
        patch(
            "warm_logic.kernel.intelligence.dht_reasoner.DHTReasoner"
        ) as mock_reasoner,
        patch(
            "warm_logic.kernel.intelligence.swarm_orchestrator.SwarmOrchestrator"
        ) as mock_orchestrator,
        patch(
            "warm_logic.kernel.observability.telemetry.TelemetryProvider"
        ) as mock_telemetry,
        patch(
            "warm_logic.kernel.substrate.heartbeat.HeartbeatMonitor"
        ) as mock_heartbeat,
        patch("warm_logic.kernel.memory.graph_vault.GraphVault") as mock_graph,
        patch("warm_logic.kernel.memory.vector_vault.VectorVault") as mock_vector,
        patch("warm_logic.kernel.sys.blackbox.BlackBox") as mock_blackbox,
    ):

        # Setup telemetry mock
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span
        mock_telemetry.return_value.get_tracer.return_value = mock_tracer

        yield {
            "autonomy_event": mock_autonomy_event,
            "eval_loop": mock_eval,
            "idea_gen": mock_idea,
            "reasoner": mock_reasoner,
            "orchestrator": mock_orchestrator,
            "telemetry": mock_telemetry,
            "heartbeat": mock_heartbeat,
            "graph": mock_graph,
            "vector": mock_vector,
            "blackbox": mock_blackbox,
        }


class TestSovereignIntelligence:
    """Test SovereignIntelligence class."""

    def test_init_sets_attributes(self, mock_dependencies):
        """Initializes with correct attributes."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_heartbeat = MagicMock()
        mock_orchestrator = MagicMock()
        mock_reasoner = MagicMock()
        mock_evoluter = MagicMock()

        si = SovereignIntelligence(
            node_id="test-node-123",
            heartbeat=mock_heartbeat,
            orchestrator=mock_orchestrator,
            reasoner=mock_reasoner,
            evoluter=mock_evoluter,
        )

        assert si.node_id == "test-node-123"
        assert si.heartbeat is mock_heartbeat
        assert si.orchestrator is mock_orchestrator
        assert si.reasoner is mock_reasoner
        assert si.evoluter is mock_evoluter
        assert si.running is False

    def test_init_creates_memory_systems(self, mock_dependencies):
        """Creates memory and audit systems."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )

        assert si.memory is not None
        assert si.graph is not None
        assert si.audit_log is not None

    def test_stop_sets_running_false(self, mock_dependencies):
        """stop() sets running to False."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )

        si.running = True
        si.stop()

        assert si.running is False

    def test_stop_logs_shutdown(self, mock_dependencies):
        """stop() logs shutdown event."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )

        si.stop()

        si.audit_log.log.assert_called()
        call_arg = si.audit_log.log.call_args[0][0]
        assert call_arg["action"] == "shutdown"

    def test_process_goal_submits_to_orchestrator(self, mock_dependencies):
        """process_goal() submits to swarm orchestrator."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_orchestrator = MagicMock()
        mock_orchestrator.submit_goal.return_value = "plan_123"

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=mock_orchestrator,
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )
        si.memory = MagicMock()
        si.memory.query_thoughts.return_value = []

        result = si.process_goal("Implement feature X")

        assert result == "plan_123"
        mock_orchestrator.submit_goal.assert_called_once_with("Implement feature X")

    def test_process_goal_queries_memory(self, mock_dependencies):
        """process_goal() queries similar memories."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_memory = MagicMock()
        mock_memory.query_thoughts.return_value = ["Previous similar goal"]

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )
        si.memory = mock_memory
        si.orchestrator.submit_goal.return_value = "plan_1"

        si.process_goal("Test goal")

        mock_memory.query_thoughts.assert_called_once_with("Test goal", n_results=1)

    def test_process_goal_stores_plan(self, mock_dependencies):
        """process_goal() stores plan in memory."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_memory = MagicMock()
        mock_memory.query_thoughts.return_value = []

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )
        si.memory = mock_memory
        si.orchestrator.submit_goal.return_value = "plan_abc"

        si.process_goal("My goal")

        mock_memory.store_plan.assert_called_once()
        assert "My goal" in mock_memory.store_plan.call_args[0]

    def test_process_goal_audits_action(self, mock_dependencies):
        """process_goal() logs to audit."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )
        si.memory = MagicMock()
        si.memory.query_thoughts.return_value = []
        si.orchestrator.submit_goal.return_value = "plan_x"

        si.process_goal("Audit this goal")

        si.audit_log.log.assert_called()
        call_arg = si.audit_log.log.call_args[0][0]
        assert call_arg["action"] == "process_goal"
        assert call_arg["goal"] == "Audit this goal"

    def test_process_optimization_triggers_evolution(self, mock_dependencies):
        """process_optimization() calls evaluator."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_evoluter = MagicMock()
        mock_evoluter.evaluate_and_evolve.return_value = True

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=mock_evoluter,
        )
        si.memory = MagicMock()
        si.graph = MagicMock()

        result = si.process_optimization("module_a", "func_b")

        assert result is True
        mock_evoluter.evaluate_and_evolve.assert_called_once_with("module_a", "func_b")

    def test_process_optimization_stores_thought(self, mock_dependencies):
        """process_optimization() stores result in memory."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_memory = MagicMock()
        mock_evoluter = MagicMock()
        mock_evoluter.evaluate_and_evolve.return_value = True

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=mock_evoluter,
        )
        si.memory = mock_memory
        si.graph = MagicMock()

        si.process_optimization("mod", "func")

        mock_memory.store_thought.assert_called()

    def test_process_optimization_links_graph_on_success(self, mock_dependencies):
        """process_optimization() links concepts in graph on success."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_graph = MagicMock()
        mock_evoluter = MagicMock()
        mock_evoluter.evaluate_and_evolve.return_value = True

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=mock_evoluter,
        )
        si.memory = MagicMock()
        si.graph = mock_graph

        si.process_optimization("my_module", "my_func")

        mock_graph.add_concept.assert_called()
        mock_graph.link_concepts.assert_called()

    def test_process_optimization_no_graph_on_failure(self, mock_dependencies):
        """process_optimization() doesn't link graph on failure."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_graph = MagicMock()
        mock_evoluter = MagicMock()
        mock_evoluter.evaluate_and_evolve.return_value = False

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=mock_evoluter,
        )
        si.memory = MagicMock()
        si.graph = mock_graph

        si.process_optimization("fail_mod", "fail_func")

        mock_graph.add_concept.assert_not_called()

    def test_synthesize_thought_publishes_insight(self, mock_dependencies):
        """synthesize_thought() publishes to reasoner."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_reasoner = MagicMock()
        mock_reasoner.synthesize_verdict.return_value = "consensus_verdict"

        si = SovereignIntelligence(
            node_id="node123",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=mock_reasoner,
            evoluter=MagicMock(),
        )
        si.memory = MagicMock()

        result = si.synthesize_thought("ethics_topic")

        assert result == "consensus_verdict"
        mock_reasoner.publish_insight.assert_called_once()
        mock_reasoner.synthesize_verdict.assert_called_once_with("ethics_topic")

    def test_synthesize_thought_memorizes_verdict(self, mock_dependencies):
        """synthesize_thought() stores verdict in memory."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_memory = MagicMock()
        mock_reasoner = MagicMock()
        mock_reasoner.synthesize_verdict.return_value = "final_answer"

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=mock_reasoner,
            evoluter=MagicMock(),
        )
        si.memory = mock_memory

        si.synthesize_thought("some_topic")

        mock_memory.store_thought.assert_called()
        call_args = mock_memory.store_thought.call_args[0]
        assert "final_answer" in call_args[0]

    def test_synthesize_thought_audits(self, mock_dependencies):
        """synthesize_thought() logs to audit."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_reasoner = MagicMock()
        mock_reasoner.synthesize_verdict.return_value = "verdict"

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=MagicMock(),
            orchestrator=MagicMock(),
            reasoner=mock_reasoner,
            evoluter=MagicMock(),
        )
        si.memory = MagicMock()

        si.synthesize_thought("topic_x")

        si.audit_log.log.assert_called()
        call_arg = si.audit_log.log.call_args[0][0]
        assert call_arg["action"] == "synthesize_thought"
        assert call_arg["topic"] == "topic_x"

    def test_tick_restarts_unstable_heartbeat(self, mock_dependencies):
        """_tick() restarts heartbeat if not alive."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_heartbeat = MagicMock()
        mock_heartbeat.is_alive.return_value = False

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=mock_heartbeat,
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )

        si._tick()

        mock_heartbeat.start.assert_called_once()
        si.audit_log.log.assert_called()

    def test_tick_no_restart_if_alive(self, mock_dependencies):
        """_tick() doesn't restart heartbeat if alive."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_heartbeat = MagicMock()
        mock_heartbeat.is_alive.return_value = True

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=mock_heartbeat,
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )

        si._tick()

        mock_heartbeat.start.assert_not_called()

    def test_start_eternal_run_triggers_autonomy_event(self, mock_dependencies):
        """start_eternal_run() triggers the autonomy event."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_heartbeat = MagicMock()
        mock_heartbeat.is_alive.return_value = True

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=mock_heartbeat,
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )
        si.memory = MagicMock()

        # Stop immediately after one tick
        def stop_after_tick():
            si._tick()
            si.running = False

        with patch.object(si, "_tick", side_effect=stop_after_tick):
            si.start_eternal_run()

        si.autonomy_event.trigger.assert_called_once()

    def test_start_eternal_run_logs_awakening(self, mock_dependencies):
        """start_eternal_run() logs awakening event."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_heartbeat = MagicMock()
        mock_heartbeat.is_alive.return_value = True

        si = SovereignIntelligence(
            node_id="test-node",
            heartbeat=mock_heartbeat,
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )
        si.memory = MagicMock()

        # Stop immediately
        si._loop_delay = 0
        call_count = [0]

        def stop_after_tick():
            call_count[0] += 1
            if call_count[0] > 0:
                si.running = False

        with patch.object(si, "_tick", side_effect=stop_after_tick):
            si.start_eternal_run()

        # Should have stored awakening thought
        si.memory.store_thought.assert_called()
        si.audit_log.log.assert_called()

    def test_start_eternal_run_handles_keyboard_interrupt(self, mock_dependencies):
        """start_eternal_run() handles KeyboardInterrupt gracefully."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_heartbeat = MagicMock()

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=mock_heartbeat,
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )
        si.memory = MagicMock()

        with patch.object(si, "_tick", side_effect=KeyboardInterrupt):
            si.start_eternal_run()

        # KeyboardInterrupt exits gracefully but running stays True
        # (implementation logs and exits, doesn't set running=False)
        assert si.running is True

    def test_start_eternal_run_handles_exception(self, mock_dependencies):
        """start_eternal_run() handles exceptions and stops."""
        from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

        mock_heartbeat = MagicMock()

        si = SovereignIntelligence(
            node_id="node1",
            heartbeat=mock_heartbeat,
            orchestrator=MagicMock(),
            reasoner=MagicMock(),
            evoluter=MagicMock(),
        )
        si.memory = MagicMock()

        with patch.object(si, "_tick", side_effect=RuntimeError("Critical error")):
            si.start_eternal_run()

        # Should have stopped running due to exception
        assert si.running is False
