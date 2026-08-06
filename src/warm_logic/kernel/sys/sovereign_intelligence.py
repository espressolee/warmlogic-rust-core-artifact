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
import time

from warm_logic.kernel.events.autonomy_event import AutonomyEvent
from warm_logic.kernel.evolution.evaluation_loop import EvaluationLoop
from warm_logic.kernel.intelligence.dht_reasoner import DHTReasoner
from warm_logic.kernel.intelligence.swarm_orchestrator import SwarmOrchestrator
from warm_logic.kernel.observability.telemetry import TelemetryProvider
from warm_logic.kernel.substrate.heartbeat import HeartbeatMonitor

logger = logging.getLogger("SovereignIntelligence")
tracer = TelemetryProvider().get_tracer("warmlogic.kernel.sys.sovereign")


from warm_logic.kernel.memory.graph_vault import GraphVault  # noqa: E402
from warm_logic.kernel.memory.vector_vault import VectorVault  # noqa: E402
from warm_logic.kernel.sys.blackbox import BlackBox  # noqa: E402


class SovereignIntelligence:
    """
    The Master Daemon.
    Orchestrates the entire autonomous lifecycle:
    Propagate -> Reason -> Evolve -> Repeat.
    Now with Long-Term Memory.
    """

    def __init__(
        self,
        node_id: str,
        heartbeat: HeartbeatMonitor,
        orchestrator: SwarmOrchestrator,
        reasoner: DHTReasoner,
        evoluter: EvaluationLoop,
    ):
        self.node_id = node_id
        self.heartbeat = heartbeat
        self.orchestrator = orchestrator
        self.reasoner = reasoner
        self.evoluter = evoluter
        self.autonomy_event = AutonomyEvent()
        self.memory = VectorVault(persist_path="data/memory/sovereign_db")
        self.graph = GraphVault(persist_path="data/memory/sovereign_graph.json")
        self.audit_log = BlackBox(ledger_path="data/audit/blackbox.jsonl")

        self.running = False
        self._loop_delay = 1.0  # Adjust for real world (e.g. 5.0)

    def start_eternal_run(self) -> None:
        """
        Activates the convergence Event and enters the infinite loop.
        """
        self.autonomy_event.trigger()
        self.running = True

        logger.info(f"[Sovereign] Node {self.node_id} entering long-running Run...")

        # Log awakening
        event = {
            "event": "awakening",
            "timestamp": time.time(),
            "node_id": self.node_id,
        }
        self.memory.store_thought(
            f"Sovereign Node {self.node_id} awakened. convergence engaged.",
            event,
        )
        self.audit_log.log(event)

        try:
            while self.running:
                self._tick()
                time.sleep(self._loop_delay)
        except KeyboardInterrupt:
            logger.info("[Sovereign] Manual interrupt. Halting long-running Run.")
        except Exception as e:
            logger.critical(f"[Sovereign] Critical Failure in Loop: {e}")
            self.running = False

    def _tick(self) -> None:
        """
        One cycle of the autonomous mind.
        """
        # 1. Biological maintenance (Heartbeat)
        if not self.heartbeat.is_alive():
            logger.warning(
                "❤️ [Sovereign] Heartbeat unstable. Attempting resuscitation..."
            )
            self.heartbeat.start()
            self.audit_log.log({"action": "heartbeat_restart", "reason": "unstable"})

        # 2. Cognitive Loop (Orchestration)
        with tracer.start_as_current_span("loop_cycle"):
            # Check if there are active plans or new goals
            # In real system, reading from task.md or self-generated goals
            # For verification, we expose a method to inject goals externally
            pass

    def process_goal(self, goal: str) -> str:
        """
        Injects a goal into the cognitive loop.
        """
        # [Phase 67] Recall similar goals
        similar = self.memory.query_thoughts(goal, n_results=1)
        if similar:
            logger.info(f"[Sovereign] Recalled relevant memory: {similar}")

        plan_id = self.orchestrator.submit_goal(goal)

        # Store intent
        self.memory.store_plan(goal, ["Dispatched to Swarm"], "In Progress")

        # Audit
        self.audit_log.log(
            {
                "action": "process_goal",
                "goal": goal,
                "recalled": bool(similar),
                "plan_id": plan_id,
            }
        )

        with tracer.start_as_current_span("process_goal") as span:
            span.set_attribute("goal", goal)
            span.set_attribute("recalled", bool(similar))
            span.set_attribute("plan_id", plan_id)

        return plan_id

    def process_optimization(self, module_name: str, func_name: str) -> bool:
        """
        Triggers an evolution attempt.
        """
        result = self.evoluter.evaluate_and_evolve(module_name, func_name)

        # Store evolution event
        self.memory.store_thought(
            f"Optimized {module_name}.{func_name}. Success: {result}",
            {"type": "evolution", "target": func_name, "success": result},
        )

        # [Phase 68] Graph Linking
        if result:
            self.graph.add_concept(module_name, type="Module")
            self.graph.add_concept(func_name, type="Function")
            self.graph.link_concepts(module_name, func_name, "CONTAINS")
            self.graph.link_concepts(func_name, "Optimization", "ACHIEVED")

        # Audit
        self.audit_log.log(
            {
                "action": "evolution_attempt",
                "target": f"{module_name}.{func_name}",
                "success": result,
            }
        )

        return result

    def synthesize_thought(self, topic: str) -> str:
        """
        Triggers distributed reasoning.
        """
        # Publish local insight (simulation)
        self.reasoner.publish_insight(topic, f"Insight from {self.node_id}")

        verdict = self.reasoner.synthesize_verdict(topic)

        # Memorize the verdict
        self.memory.store_thought(
            f"Verdict on {topic}: {verdict}", {"type": "consensus", "topic": topic}
        )

        # Audit
        self.audit_log.log(
            {"action": "synthesize_thought", "topic": topic, "verdict": verdict}
        )

        return verdict

    def stop(self) -> None:
        self.running = False
        self.audit_log.log({"action": "shutdown", "reason": "command"})
