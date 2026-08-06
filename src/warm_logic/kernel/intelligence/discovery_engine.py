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
[Phase 44] Level 5 Strategic Discovery Engine.
Elevates the system from "Code Analysis" (Level 3) to "Strategic Goal Setting" (Level 5).
Uses LLM-based reasoning to propose architectural improvements based on system context.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import Local Inference Client
try:
    from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient
except ImportError:
    # Fail gracefully if bridge is missing (fallback mode)
    LocalInferenceClient = None

logger = logging.getLogger("StrategicDiscovery")


@dataclass
class StrategicTask:
    """A high-level strategic task proposed by the Discovery Engine."""

    id: str
    title: str
    description: str
    rationale: str  # Why is this necessary?
    risk_assessment: str  # What could go wrong?
    priority: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    source: str = "StrategicDiscoveryEngine"
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "proposed"


class StrategicDiscoveryEngine:
    """
    [] Strategic Goal Setting Engine.
    Reads system documentation and state to propose high-level architectural moves.
    """

    def __init__(self, workspace: str = ".", llm_client: Optional[Any] = None):
        self.workspace = Path(workspace)
        self.llm_client = llm_client or (
            LocalInferenceClient() if LocalInferenceClient else None
        )
        self._context_cache: Dict[str, str] = {}

    def load_context(self) -> str:
        """
        Loads critical system context files to form the 'World Model'.
        """
        context_files = {
            "ARCHITECTURE": "docs/ARCHITECTURE.md",
            "TASK_STATUS": "docs/task.md",  # Usually located in brain artifact, but checked relative to workspace or hardcoded paths if needed.
            # Note: task.md is dynamic. We will try to find the active task.md if possible, or skip.
            # For now, we assume standard doc paths. If task.md is in artifacts, we might need a way to find it.
            # We will use project docs for now.
            "AUDIT_LOG": "docs/SIMULATION_AUDIT.md",
        }

        # Try to find task.md in artifacts if not in docs
        # This is a bit tricky since artifacts path is dynamic per session.
        # We will focus on the static docs first.

        context_str = "=== SYSTEM CONTEXT ===\n\n"

        for label, rel_path in context_files.items():
            path = self.workspace / rel_path
            if path.exists():
                content = path.read_text(encoding="utf-8")
                # Truncate to avoid context overflow (approx 2k chars per doc)
                summary = content[:3000]
                context_str += f"--- {label} ({rel_path}) ---\n{summary}\n...\n\n"
            else:
                context_str += f"--- {label} ---\n[MISSING]\n\n"

        # Add current directory structure overview
        context_str += "--- DIRECTORY STRUCTURE ---\n"
        try:
            # Simple ls -F to give structure context
            import subprocess

            res = subprocess.run(
                ["ls", "-F", str(self.workspace)], capture_output=True, text=True
            )
            context_str += res.stdout
        except Exception:
            pass

        return context_str

    def discover_strategic_goals(self) -> List[StrategicTask]:
        """
        Uses LLM to analyze context and propose strategic tasks.
        """
        if not self.llm_client:
            logger.warning("LLM client unavailable for strategic discovery.")
            return []

        context = self.load_context()

        system_prompt = (
            "You are the Strategic Core of WarmLogic (Sovereign OS). "
            "Your goal is to analyze the current system state and propose ONE to THREE "
            "critical architectural or operational improvements needed to reach the next level of maturity.\n"
            "Focus on: Robustness, Security, Autonomy, and Feature Completeness.\n"
            "Do NOT propose trivial code style fixes. Think big: 'Add Vision', 'Refactor Kernel', 'Enhance Security'."
        )

        user_prompt = (
            f"{context}\n\n"
            "Based on the context above, propose strategic tasks in the following JSON format:\n"
            "{\n"
            '  "tasks": [\n'
            "    {\n"
            '      "title": "...",\n'
            '      "description": "...",\n'
            '      "rationale": "...",\n'
            '      "risk_assessment": "...",\n'
            '      "priority": "HIGH"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Output ONLY JSON."
        )

        try:
            logger.info("[StrategicDiscovery] Reasoning about system state...")
            response = self.llm_client.generate_thought(
                prompt=user_prompt, system_prompt=system_prompt
            )

            if not response:
                return []

            # Attempt to parse potentially messy JSON
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                tasks_data = data.get("tasks", [])

                strategic_tasks = []
                for i, t in enumerate(tasks_data):
                    task = StrategicTask(
                        id=f"STRAT-{datetime.now().strftime('%Y%m%d')}-{i + 1:02d}",
                        title=t.get("title", "Untitled Strategy"),
                        description=t.get("description", ""),
                        rationale=t.get("rationale", ""),
                        risk_assessment=t.get("risk_assessment", "Unknown"),
                        priority=t.get("priority", "MEDIUM"),
                    )
                    strategic_tasks.append(task)
                    logger.info(f"[Strategy] Proposed: {task.title}")

                return strategic_tasks

        except Exception as e:
            logger.error(f"[StrategicDiscovery] Error during inference: {e}")

        return []

    def save_proposals(
        self, tasks: List[StrategicTask], path: str = "strategic_proposals.json"
    ):
        """Saves proposals to disk."""
        data = [asdict(t) for t in tasks]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path


if __name__ == "__main__":
    # verification run
    logging.basicConfig(level=logging.INFO)
    engine = StrategicDiscoveryEngine()
    print("Loading Context...")
    print(engine.load_context()[:500] + "...")
