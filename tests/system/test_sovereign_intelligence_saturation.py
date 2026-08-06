import importlib
from unittest.mock import MagicMock, patch

import pytest


class TestSovereignIntelligenceSaturation:
    @pytest.fixture
    def mock_deps(self):
        return {
            "heartbeat": MagicMock(),
            "orchestrator": MagicMock(),
            "reasoner": MagicMock(),
            "evoluter": MagicMock(),
        }

    @pytest.fixture
    def si(self, mock_deps):
        module = importlib.import_module("warm_logic.kernel.sys.sovereign_intelligence")
        # Patching sub-vaults and audit log to avoid disk I/O
        with (
            patch.object(module, "VectorVault"),
            patch.object(module, "GraphVault"),
            patch.object(module, "BlackBox"),
        ):
            return module.SovereignIntelligence(node_id="test_node", **mock_deps)

    def test_start_eternal_run_success(self, si):
        """Test successful start and one tick of long-running loop."""
        with patch("time.sleep") as mock_sleep:
            # Make the loop run once then stop
            def stop_loop(*args):
                si.running = False

            mock_sleep.side_effect = stop_loop

            si.start_eternal_run()

            assert si.autonomy_event.triggered
            si.memory.store_thought.assert_called()
            si.audit_log.log.assert_called()
            mock_sleep.assert_called_once()

    def test_start_eternal_run_keyboard_interrupt(self, si):
        """Test KeyboardInterrupt handling in long-running loop."""
        with patch("time.sleep", side_effect=KeyboardInterrupt):
            si.running = True
            si.start_eternal_run()
            # Should catch and log, not raise
            assert si.running is True  # it stays true since loop broke from interrupt

    def test_start_eternal_run_exception(self, si):
        """Test general exception handling in long-running loop."""
        with patch("time.sleep", side_effect=ValueError("Test Error")):
            si.running = True
            si.start_eternal_run()
            # Should set running to False on critical failure
            assert si.running is False

    def test_tick_resuscitation(self, si):
        """Test heartbeat resuscitation path in _tick."""
        si.heartbeat.is_alive.return_value = False

        si._tick()

        si.heartbeat.start.assert_called_once()
        si.audit_log.log.assert_any_call(
            {"action": "heartbeat_restart", "reason": "unstable"}
        )

    def test_process_goal_recall_success(self, si):
        """Test process_goal with memory recall."""
        si.memory.query_thoughts.return_value = ["Previous Plan"]
        si.orchestrator.submit_goal.return_value = "plan_123"

        plan_id = si.process_goal("Win at Chess")

        assert plan_id == "plan_123"
        si.memory.store_plan.assert_called_with(
            "Win at Chess", ["Dispatched to Swarm"], "In Progress"
        )
        si.audit_log.log.assert_called()

    def test_process_goal_no_recall(self, si):
        """Test process_goal without memory recall."""
        si.memory.query_thoughts.return_value = []

        si.process_goal("New Goal")

        # Verify audit log shows recalled=False
        si.audit_log.log.assert_called()
        call_args = si.audit_log.log.call_args[0][0]
        assert call_args["recalled"] is False

    def test_process_optimization_success(self, si):
        """Test process_optimization success path (graph linking)."""
        si.evoluter.evaluate_and_evolve.return_value = True

        result = si.process_optimization("module_a", "func_b")

        assert result is True
        si.graph.add_concept.assert_any_call("module_a", type="Module")
        si.graph.add_concept.assert_any_call("func_b", type="Function")
        si.graph.link_concepts.assert_any_call("module_a", "func_b", "CONTAINS")
        si.graph.link_concepts.assert_any_call("func_b", "Optimization", "ACHIEVED")

    def test_process_optimization_failure(self, si):
        """Test process_optimization failure path (no graph linking)."""
        si.evoluter.evaluate_and_evolve.return_value = False

        result = si.process_optimization("module_a", "func_b")

        assert result is False
        si.graph.add_concept.assert_not_called()

    def test_synthesize_thought(self, si):
        """Test synthesize_thought logic."""
        si.reasoner.synthesize_verdict.return_value = "The Verdict"

        verdict = si.synthesize_thought("Meaning of Life")

        assert verdict == "The Verdict"
        si.reasoner.publish_insight.assert_called_with(
            "Meaning of Life", f"Insight from {si.node_id}"
        )
        si.memory.store_thought.assert_called()
        si.audit_log.log.assert_any_call(
            {
                "action": "synthesize_thought",
                "topic": "Meaning of Life",
                "verdict": "The Verdict",
            }
        )

    def test_stop(self, si):
        """Test stop behavior."""
        si.running = True
        si.stop()
        assert si.running is False
        si.audit_log.log.assert_any_call({"action": "shutdown", "reason": "command"})
