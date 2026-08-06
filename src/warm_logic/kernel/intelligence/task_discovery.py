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
"""
[Phase A4: Agent ] Self-Directed Task Discovery.
Enables autonomous identification and proposal of improvement tasks.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SovereignTaskDiscovery")


@dataclass
class DiscoveredTask:
    """A task autonomously identified by the system."""

    id: str
    title: str
    description: str
    priority: str  # "HIGH", "MEDIUM", "LOW"
    category: str  # "bug", "improvement", "feature", "maintenance"
    source: str  # What triggered this discovery
    discovered_at: datetime = field(default_factory=datetime.now)
    confidence: float = 0.5  # How confident the system is
    suggested_actions: List[str] = field(default_factory=list)
    status: str = "pending"  # "pending", "approved", "rejected", "completed"


@dataclass
class TaskDiscoveryResult:
    """Result of a discovery scan."""

    tasks: List[DiscoveredTask]
    scan_duration_ms: float
    sources_scanned: List[str]


class SelfDirectedTaskEngine:
    """
    [] Autonomous Task Discovery Engine.

    Scans the codebase and system state to identify:
    - Missing tests
    - TODO/FIXME comments
    - Deprecated patterns
    - Performance opportunities
    - Security concerns
    - Documentation gaps
    """

    def __init__(
        self,
        workspace: str = ".",
        llm_client: Optional[Any] = None,
    ):
        self.workspace = Path(workspace)
        self.llm_client = llm_client
        self._discovered_tasks: List[DiscoveredTask] = []
        self._task_counter = 0

    def _get_llm_client(self):
        """Lazy load LLM client."""
        if self.llm_client is None:
            try:
                from warm_logic.kernel.intelligence.llm_bridge import (
                    LocalInferenceClient,
                )

                self.llm_client = LocalInferenceClient()
            except ImportError:
                logger.warning("LLM client unavailable for task analysis")
                return None
        return self.llm_client

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        self._task_counter += 1
        return f"TD-{datetime.now().strftime('%Y%m%d')}-{self._task_counter:04d}"

    def scan_todos(self) -> List[DiscoveredTask]:
        """Scan for TODO/FIXME/HACK comments."""
        tasks = []
        patterns = ["TODO", "FIXME", "HACK", "XXX", "BUG"]

        import subprocess

        for pattern in patterns:
            try:
                result = subprocess.run(
                    [
                        "grep",
                        "-rn",
                        "--include=*.py",
                        "--include=*.rs",
                        "--exclude-dir=.git",
                        "--exclude-dir=__pycache__",
                        pattern,
                        str(self.workspace),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue

                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        file_path, line_num, content = parts
                        tasks.append(
                            DiscoveredTask(
                                id=self._generate_task_id(),
                                title=f"{pattern} in {Path(file_path).name}:{line_num}",
                                description=content.strip()[:200],
                                priority=(
                                    "MEDIUM" if pattern in ["TODO", "FIXME"] else "LOW"
                                ),
                                category="maintenance",
                                source=f"todo_scan:{file_path}",
                                confidence=0.9,
                                suggested_actions=[
                                    f"Review and resolve: {file_path}:{line_num}"
                                ],
                            )
                        )

            except Exception as e:
                logger.debug(f"TODO scan error for {pattern}: {e}")

        return tasks[:20]  # Limit to avoid overwhelming

    def scan_missing_tests(self) -> List[DiscoveredTask]:
        """Identify Python functions without corresponding tests."""
        tasks = []
        import subprocess

        try:
            # Find all Python files
            result = subprocess.run(
                ["find", str(self.workspace), "-name", "*.py", "-type", "f"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            src_files = []
            test_files = set()

            for f in result.stdout.strip().split("\n"):
                if not f or "__pycache__" in f or ".git" in f:
                    continue
                if "test_" in f or "/tests/" in f:
                    test_files.add(Path(f).stem.replace("test_", ""))
                else:
                    src_files.append(f)

            # Find modules without tests
            for src in src_files[:50]:
                module_name = Path(src).stem
                if module_name.startswith("_"):
                    continue
                if module_name not in test_files:
                    tasks.append(
                        DiscoveredTask(
                            id=self._generate_task_id(),
                            title=f"Missing tests for {module_name}.py",
                            description=f"No test file found for module: {src}",
                            priority="MEDIUM",
                            category="improvement",
                            source=f"test_coverage_scan:{src}",
                            confidence=0.7,
                            suggested_actions=[
                                f"Create tests/test_{module_name}.py",
                                "Add unit tests for key functions",
                            ],
                        )
                    )

        except Exception as e:
            logger.debug(f"Test scan error: {e}")

        return tasks[:10]

    def scan_security_patterns(self) -> List[DiscoveredTask]:
        """Scan for common security anti-patterns."""
        tasks = []
        import subprocess

        security_patterns = [
            ("eval(", "HIGH", "Dynamic code execution - potential injection"),
            ("exec(", "HIGH", "Dynamic code execution - potential injection"),
            ("pickle.load", "MEDIUM", "Unsafe deserialization"),
            ("shell=True", "MEDIUM", "Shell injection risk"),
            ("pass" + "word=", "LOW", "Hardcoded credential check"),  # noqa: S105
        ]

        for pattern, priority, desc in security_patterns:
            try:
                result = subprocess.run(
                    [
                        "grep",
                        "-rn",
                        "--include=*.py",
                        "--exclude-dir=.git",
                        pattern,
                        str(self.workspace),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                for line in result.stdout.strip().split("\n")[:3]:
                    if not line:
                        continue
                    parts = line.split(":", 2)
                    if len(parts) >= 2:
                        tasks.append(
                            DiscoveredTask(
                                id=self._generate_task_id(),
                                title=f"Security concern: {pattern} usage",
                                description=f"{desc}: {parts[0]}:{parts[1]}",
                                priority=priority,
                                category="bug",
                                source=f"security_scan:{parts[0]}",
                                confidence=0.6,
                                suggested_actions=[
                                    "Review usage and refactor if needed"
                                ],
                            )
                        )

            except Exception as e:
                logger.debug(f"Security pattern scan error: {e}")

        return tasks

    def discover_all(self) -> TaskDiscoveryResult:
        """Run all discovery scans."""
        import time

        start = time.time()
        all_tasks: List[DiscoveredTask] = []
        sources = []

        # Run scans
        logger.info("[TaskDiscovery] Starting autonomous scan...")

        todos = self.scan_todos()
        all_tasks.extend(todos)
        if todos:
            sources.append(f"todos:{len(todos)}")

        tests = self.scan_missing_tests()
        all_tasks.extend(tests)
        if tests:
            sources.append(f"tests:{len(tests)}")

        security = self.scan_security_patterns()
        all_tasks.extend(security)
        if security:
            sources.append(f"security:{len(security)}")

        # Sort by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        all_tasks.sort(key=lambda t: priority_order.get(t.priority, 3))

        self._discovered_tasks = all_tasks
        duration_ms = (time.time() - start) * 1000

        logger.info(
            f"🔍 [TaskDiscovery] Found {len(all_tasks)} tasks in {duration_ms:.0f}ms"
        )

        return TaskDiscoveryResult(
            tasks=all_tasks,
            scan_duration_ms=duration_ms,
            sources_scanned=sources,
        )

    def get_summary(self) -> str:
        """Generate a human-readable summary of discovered tasks."""
        if not self._discovered_tasks:
            return "No tasks discovered. Run discover_all() first."

        lines = ["# Discovered Tasks\n"]

        # Group by priority
        high = [t for t in self._discovered_tasks if t.priority == "HIGH"]
        medium = [t for t in self._discovered_tasks if t.priority == "MEDIUM"]
        low = [t for t in self._discovered_tasks if t.priority == "LOW"]

        if high:
            lines.append(f"## 🔴 HIGH Priority ({len(high)})\n")
            for t in high[:5]:
                lines.append(f"- **{t.title}**: {t.description[:100]}")

        if medium:
            lines.append(f"\n## 🟠 MEDIUM Priority ({len(medium)})\n")
            for t in medium[:10]:
                lines.append(f"- **{t.title}**: {t.description[:80]}")

        if low:
            lines.append(f"\n## 🟢 LOW Priority ({len(low)})\n")
            for t in low[:5]:
                lines.append(f"- {t.title}")

        return "\n".join(lines)

    def export_json(self, path: str = "discovered_tasks.json") -> str:
        """Export discovered tasks to JSON."""
        data = [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "priority": t.priority,
                "category": t.category,
                "source": t.source,
                "confidence": t.confidence,
                "suggested_actions": t.suggested_actions,
                "status": t.status,
            }
            for t in self._discovered_tasks
        ]

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        return path


def discover_tasks(workspace: str = ".") -> TaskDiscoveryResult:
    """Convenience function for quick task discovery."""
    engine = SelfDirectedTaskEngine(workspace)
    return engine.discover_all()


class AutonomousGoalFormation:
    """
    [Phase 98.3] Proactive Goal Formation.
    Proposes the next goal based on:
    1. Discovered tasks (high priority first)
    2. Memory context (what has been done)
    3. Time-based priorities (stale tasks)
    """

    def __init__(self, workspace: str = ".", memory=None):
        self.task_engine = SelfDirectedTaskEngine(workspace)
        self.memory = memory
        self._last_scan = None
        logger.info("[AutonomousGoal] Goal Formation Engine Active.")

    def analyze_and_propose(self) -> Dict[str, Any]:
        """
        Analyze system state and propose the next goal.
        Returns a structured goal proposal.
        """
        # 1. Discover current tasks
        result = self.task_engine.discover_all()
        self._last_scan = result

        # 2. Get context from memory (if available)
        context = ""
        if self.memory:
            try:
                context = self.memory.retrieve_context("recent work completed")
            except Exception:
                pass

        # 3. Select highest priority unaddressed task
        high_priority = [t for t in result.tasks if t.priority == "HIGH"]
        medium_priority = [t for t in result.tasks if t.priority == "MEDIUM"]

        proposed_goal = None
        rationale = ""

        if high_priority:
            proposed_goal = high_priority[0]
            rationale = "Security/critical issue detected"
        elif medium_priority:
            proposed_goal = medium_priority[0]
            rationale = "Maintenance task improving code quality"
        elif result.tasks:
            proposed_goal = result.tasks[0]
            rationale = "General improvement opportunity"

        proposal = {
            "has_goal": proposed_goal is not None,
            "goal": proposed_goal.title if proposed_goal else "No tasks found",
            "description": proposed_goal.description if proposed_goal else "",
            "priority": proposed_goal.priority if proposed_goal else "N/A",
            "rationale": rationale,
            "suggested_actions": (
                proposed_goal.suggested_actions if proposed_goal else []
            ),
            "context_awareness": len(context) > 0,
            "total_tasks_found": len(result.tasks),
            "scan_duration_ms": result.scan_duration_ms,
        }

        logger.info(f"[AutonomousGoal] Proposed: {proposal['goal']}")
        return proposal

    def get_all_goals_summary(self) -> str:
        """Get a summary of all discovered goals."""
        if not self._last_scan:
            self.analyze_and_propose()
        return self.task_engine.get_summary()


def propose_next_goal(workspace: str = ".") -> Dict[str, Any]:
    """Convenience function: Get the agent's next self-proposed goal."""
    engine = AutonomousGoalFormation(workspace)
    return engine.analyze_and_propose()
