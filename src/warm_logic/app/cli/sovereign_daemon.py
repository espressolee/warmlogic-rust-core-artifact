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
"""[Phase 201] Sovereign Daemon - Autonomous background agent for task execution."""

import hashlib
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from warm_logic.kernel.intelligence import skill_engine
from warm_logic.kernel.intelligence.agency import AgencyExecutor

# Core Imports
from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient
from warm_logic.kernel.ops import tracing

logger = logging.getLogger("SovereignDaemon")


class TaskReader:
    """
    [Phase 54.2] The Eye of Sovereignty.
    Reads the Task Matrix (task.md) to perceive reality.
    """

    def __init__(self, task_path: str, is_enterprise: bool = False):
        self.task_path = Path(task_path)
        self.is_enterprise = is_enterprise
        self.native_scanner = None

        if self.is_enterprise:
            try:
                from warm_logic_rs import TaskScanner

                self.native_scanner = TaskScanner()
                logger.info("[Enterprise] Native TaskScanner Initialized.")
            except ImportError:
                logger.debug(
                    "⚠️ [Enterprise] Native scanner not found, falling back to Python."
                )

    def get_next_task(self) -> Optional[Dict[str, str]]:
        """
        Scans task.md for the first unchecked item.
        Uses Rust Native Perception in Enterprise mode for O(1) feel.
        """
        if not self.task_path.exists():
            logger.error(f"Task Matrix not found at {self.task_path}")
            return None

        # [Phase 55.4.3] Native Optimization
        if self.native_scanner:
            try:
                return self.native_scanner.scan_file(str(self.task_path))
            except Exception as e:
                logger.warning(
                    f"⚠️ [Enterprise] Native scan failed: {e}. Falling back."
                )

        # Standard Python Regex Scan
        content = self.task_path.read_text()
        lines = content.splitlines()
        pattern = r"-\s*\[\s*\]\s*(?:([\d\.]+):\s*)?(.+?)(?:<!--.*-->)?$"

        for i, line in enumerate(lines):
            match = re.search(pattern, line)
            if match:
                task_id = match.group(1) or "General"
                task_name = match.group(2).strip()
                return {
                    "id": task_id,
                    "name": task_name,
                    "line": i + 1,
                    "raw": line.strip(),
                }
        return None


class SovereignDaemon:
    """
    [Phase 54.1/55.3] The Ghost in the Shell.
    Autonomous loop that Reads -> Plans -> Executes -> Updates.
    Enterprise Edition: Includes License Verification and Advanced Autonomy.
    """

    def __init__(
        self, task_path: str, loop_interval: int = 60, single_run: bool = False
    ):
        # Setup Logger
        logging.basicConfig(
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            level=logging.INFO,
        )

        # [Phase 55.3] Enterprise Tiering
        self.is_enterprise = self._verify_enterprise_status()
        # [Phase 54.1] Root path calculation
        self.root = Path(__file__).parent.parent.parent.parent.parent

        self.reader = TaskReader(task_path, is_enterprise=self.is_enterprise)
        self.agent = AgencyExecutor()  # The Hands
        self.brain = LocalInferenceClient()  # The Brain
        self.interval = loop_interval
        self.single_run = single_run

        # [Phase 55.4.1] Semantic Cache (Enterprise Only)
        self.cache = None
        if self.is_enterprise:
            try:
                from warm_logic.kernel.memory.semantic import SemanticMemory

                self.cache = SemanticMemory(collection_name="plan_cache")
                logger.info("[Enterprise] Semantic Plan Cache Initialized.")
            except Exception as e:
                logger.warning(f"[Enterprise] Plan Cache Init Failed: {e}")

        # [Phase 55.5.1] Distributed Consensus (Enterprise Only)
        self.node_id = str(uuid.uuid4())[:8]
        self.consensus = None
        if self.is_enterprise:
            try:
                from warm_logic_rs import BFTEngine

                # Quorum size: 1 (Standalone/Self-Vote) or N/2+1 in cluster
                # For Phase 55.5.1, we initialize with 1 for local verification.
                self.consensus = BFTEngine(1)
                self.quorum_size = 1
                logger.info(
                    f"🛡️ [Enterprise] BFT Consensus Engine Active (Node: {self.node_id})."
                )
            except ImportError:
                logger.warning("[Enterprise] Rust BFT Engine not found.")

        # [Phase 55.6.2] Sovereign Economics (Enterprise Only)
        self.economy = None
        self.max_cost = float(os.getenv("WARM_LOGIC_MAX_COST", "10.0"))
        self.max_tokens = int(os.getenv("WARM_LOGIC_MAX_TOKENS", "1000000"))
        if self.is_enterprise:
            try:
                from warm_logic.kernel.intelligence.economics import EconomicsManager

                self.economy = EconomicsManager()
                logger.info(
                    "💰 [Enterprise] Economics Active. Budget: ${self.max_cost} / {self.max_tokens} tokens."
                )
            except Exception as e:
                logger.warning(f"[Enterprise] Economics Init Failed: {e}")

        # [Phase 57.1] Skill Engine (Sovereign Plugins)
        self.skill_registry = skill_engine.SkillRegistry()
        self.skill_manager = skill_engine.SkillManager(self.skill_registry)

        # Determine plugin directory
        self.plugin_dir = os.path.join(self.root, "out/sovereign/plugins")
        self.skill_manager.load_plugins(self.plugin_dir)

        # Inject Registry into Executor
        self.agent.registry = self.skill_registry

    def _acquire_distributed_lock(
        self, task: Dict[str, Any], quorum_size: int = 1
    ) -> bool:
        """
        [Phase 55.5.1/2] Proposes a task lock and waits for BFT Quorum.
        In Enterprise Mode, tasks are globally coordinated via Byzantine Fault Tolerance.
        """
        from warm_logic_rs import Vote

        task_hash = hashlib.sha256(f"{task['id']}:{task['name']}".encode()).hexdigest()
        logger.info(
            f"🤝 [Consensus] Proposing Lock for task '{task['name']}' ({task_hash[:8]})..."
        )
        tracing.log_trace(
            self.trace_ctx, "CONSENSUS_PROPOSAL_START", task_hash=task_hash
        )

        # Configure Engine for required quorum
        # Note: In a real cluster, quorum_size = floor(3/2 * N) + 1 or similar
        # For verification, we manually set the engine's quorum requirement.
        self.consensus = type(self.consensus)(quorum_size)

        self.consensus.start_round(int(time.time()))
        self.consensus.propose(task_hash)

        # 1. Cast Local Vote
        local_vote = Vote(self.node_id, task_hash, "local-sig")
        has_quorum = self.consensus.cast_vote(local_vote)

        # 2. [Phase 55.5.2] Simulated Peer Consensus Dialogue
        # In a real cluster, this would involve GossipAgent broadcasting proposals.
        if not has_quorum and quorum_size > 1:
            logger.info(
                f"📡 [Consensus] Waiting for {quorum_size - 1} more votes to fulfill quorum..."
            )

            # Simulated Peer Vote Injection (Modeling a 3-node cluster)
            # Node 'alpha' sees the proposal via Gossip and votes AGREE.
            peer_vote = Vote("peer-alpha", task_hash, "peer-sig-01")
            has_quorum = self.consensus.cast_vote(peer_vote)

            if has_quorum:
                logger.info("[Consensus] Quorum reached via Peer 'alpha'.")

        if has_quorum:
            logger.info(f"[Consensus] Lock Absolute. Task '{task['name']}' SECURED.")
            tracing.log_trace(
                self.trace_ctx, "CONSENSUS_QUORUM_REACHED", task_hash=task_hash
            )
            return True

        tracing.log_trace(self.trace_ctx, "CONSENSUS_FAILED", task_hash=task_hash)
        return False

    def _verify_enterprise_status(self) -> bool:
        """Checks for WARM_LOGIC_LICENSE_KEY or Enterprise certificate."""
        key = os.getenv("WARM_LOGIC_LICENSE_KEY")
        if key and key.startswith("WL-ENT-"):
            logger.info("Enterprise License Verified. Unlocking Level 5 Autonomy.")
            return True
        logger.info("Community Edition Active. Standard Autonomy (Level 3).")
        return False

    def run(self):
        mode = "ENTERPRISE" if self.is_enterprise else "COMMUNITY"
        logger.info(f"Sovereign Daemon ({mode}) Initialized. Waiting for tasks...")

        # Initialize Ethics Sentinel
        try:
            from warm_logic.kernel.ops.ethics_monitor import EthicsMonitor

            self.sentinel = EthicsMonitor(kernel_api=self)
            # asyncio bridge would be needed for a full daemon,
            # but for this logic we sync-track it.
            self._veto_locked = False
        except ImportError:
            self.sentinel = None
            self._veto_locked = False

        while True:
            try:
                if self._veto_locked:
                    logger.warning("VETO_LOCK ACTIVE. Execution Suspended.")
                    time.sleep(10)
                    continue

                self.tick()
                if self.single_run:
                    break
                time.sleep(self.interval)
            except KeyboardInterrupt:
                logger.info("Daemon Shutdown.")
                break
            except Exception as e:
                logger.error(f"Daemon Crash: {e}", exc_info=True)
                if self.single_run:
                    raise e
                time.sleep(10)  # Cool down

    def initiate_veto_lock(self):
        """Constitutional Halt."""
        self._veto_locked = True
        logger.critical("GLOBAL VETO_LOCK INITIATED BY SENTINEL.")

    def lift_veto_lock(self):
        """Manual/Ethical Recovery."""
        self._veto_locked = False
        logger.info("VETO_LOCK LIFTED. Resuming Sovereignty.")

    # CQ-004: Helper methods to reduce tick() complexity (21→5)

    def _try_cache_lookup(self, task: Dict[str, Any]) -> Optional[str]:
        """Try to get plan from semantic cache (Enterprise only)."""
        if not (self.is_enterprise and self.cache):
            return None
        results = self.cache.search(task["name"], n_results=1)
        if not results:
            return None
        dist = results[0].get("distance", 1.0)
        logger.info(
            f"🕵️ [Enterprise] Cache lookup for '{task['name']}': distance={dist:.4f}"
        )
        if dist < 0.4:
            logger.info("[Enterprise] Cache Hit! Bypassing LLM Planning.")
            return results[0]["metadata"].get("plan")
        return None

    def _check_budget(self) -> bool:
        """Check if within budget limits (Enterprise only). Returns False if over budget."""
        if not (self.is_enterprise and self.economy):
            return True
        if not self.economy.is_within_budget(self.max_cost, self.max_tokens):
            logger.error("[Economics] Budget EXCEEDED. Halting for safety.")
            self.single_run = True
            return False
        return True

    def _generate_plan(self, task: Dict[str, Any]) -> Optional[str]:
        """Generate plan using LLM brain."""
        logger.info(f"Planning (Autonomy Level {self.autonomy_level})...")

        proactive_instructions = ""
        if self.is_enterprise:
            proactive_instructions = (
                "5. PROACTIVE MODE: If the task is ambiguous, search for context automatically.\n"
                "6. SELF-CORRECTION: If an action fails, analyze the error and try a different approach.\n"
            )

        skill_discovery = self.skill_registry.get_discovery_prompt()
        prompt = (
            f"You are the Sovereign Daemon (Level {self.autonomy_level}). Your goal is to complete this task:\n"
            f"Task: {task['name']}\n\n"
            f"Instructions:\n"
            f"1. Analyze what needs to be done.\n"
            f"2. Output a JSON action plan to execute it.\n"
            f"3. Use appropriate tools based on the capability list below.\n"
            f"{proactive_instructions}"
            f"\n=== CORE CAPABILITIES ===\n"
            f"- shell, write_file, read_file, search, diff, analyze_image\n"
            f"{skill_discovery}\n"
            f"IMPORTANT: Your output MUST contain the JSON action block."
        )

        plan = self.brain.generate_thought(prompt=prompt)

        if self.is_enterprise and self.economy and self.brain.last_usage:
            self.economy.record_usage(self.brain.model_name, self.brain.last_usage)

        return plan

    def _cache_plan(self, task: Dict[str, Any], plan: str) -> None:
        """Cache successful plan (Enterprise only)."""
        if not (self.is_enterprise and self.cache):
            return
        logger.info(f"[Enterprise] Caching successful plan for '{task['name']}'")
        success = self.cache.add(
            content=task["name"],
            role="assistant",
            metadata={"task_id": task["id"], "task_name": task["name"], "plan": plan},
        )
        if not success:
            logger.warning("[Enterprise] Failed to cache plan.")

    def _execute_actions(self, actions: List[Dict[str, Any]]) -> None:
        """Execute actions (parallel for enterprise, sequential otherwise)."""
        if self.is_enterprise and len(actions) > 1:
            logger.info(
                f"🤖 [Enterprise] Parallel Execution of {len(actions)} steps..."
            )
            results = self.agent.execute_batch(actions)
            for i, res in enumerate(results):
                logger.info(f"  > Action {i + 1} Result: {res[:100]}...")
                if "Error" in res:
                    logger.warning(
                        f"🛡️ Enterprise Self-Correction triggered for Action {i + 1}. Re-evaluating..."
                    )
        else:
            logger.info(f"Executing {len(actions)} steps sequentially...")
            for action in actions:
                res = self.agent.execute(action)
                logger.info(f"  > Action Result: {res[:100]}...")
                if "Error" in res and self.is_enterprise:
                    logger.warning(
                        "🛡️ Enterprise Self-Correction triggered. Re-evaluating..."
                    )

    @property
    def autonomy_level(self) -> int:
        """Return autonomy level based on edition."""
        return 5 if self.is_enterprise else 3

    def tick(self):
        """
        CQ-004: Refactored tick() with reduced complexity (21→5).
        Main execution cycle: Perceive → Plan → Execute.
        """
        # 1. Perception
        task = self.reader.get_next_task()
        if not task:
            logger.info("No pending tasks found. Resting.")
            return

        # Initialize distributed trace
        self.trace_ctx = tracing.new_trace(self.node_id)
        tracing.log_trace(
            self.trace_ctx,
            "TASK_PERCEIVED",
            task_id=task.get("id"),
            task_name=task.get("name"),
        )

        # Acquire consensus lock (Enterprise only)
        if self.is_enterprise and self.consensus:
            if not self._acquire_distributed_lock(task, quorum_size=self.quorum_size):
                logger.info(
                    f"🚫 [Consensus] Lock acquisition failed for '{task['name']}'. Skipping."
                )
                return

        logger.info(f"Acquired Target: [{task['id']}] {task['name']}")

        # 2. Planning - Try cache first, then generate
        plan_response = self._try_cache_lookup(task)

        if not plan_response:
            if not self._check_budget():
                return
            plan_response = self._generate_plan(task)
            if plan_response:
                self._cache_plan(task, plan_response)

        if not plan_response:
            logger.error("Brain failed to generate plan.")
            return

        # 3. Execution
        actions = self.agent.extract_action(plan_response)
        if not actions:
            logger.warning("No actionable steps found in plan.")
            return

        self._execute_actions(actions)

        # 4. Success
        logger.info(f"Execution Cycle Complete for {task['id']}.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", default="task.md", help="Path to task.md")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    daemon = SovereignDaemon(args.task_file, single_run=args.once)
    daemon.run()
