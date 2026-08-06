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
import json
from pathlib import Path
from typing import Any, Dict, List


class AutoTasker:
    """
    Analyzes Knowledge Graph data and correlates it with AI Roadmap
    to suggest the most impactful next tasks.
    """

    def __init__(self, kg_path: str, roadmap_path: str):
        self.kg_path = Path(kg_path)
        self.roadmap_path = Path(roadmap_path)
        self.kg_data = self._load_json(kg_path)
        self.roadmap_text = self.roadmap_path.read_text(errors="ignore")

    def _load_json(self, path: str) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)

    def analyze(self) -> List[Dict[str, Any]]:
        """Identify gaps and priorities."""
        nodes = self.kg_data.get("nodes", {})
        edges = self.kg_data.get("edges", [])

        gaps = []

        # 1. Finding code files without verification (Orphans)
        code_nodes = {k: v for k, v in nodes.items() if v.get("type") == "code"}
        verification_edges = [e for e in edges if e.get("type") == "verification"]

        verified_modules = {e["to"] for e in verification_edges}

        for node_id, node in code_nodes.items():
            pkg_name = (
                node["path"].replace("/", ".").replace("src.", "").replace(".py", "")
            )
            if pkg_name not in verified_modules and "warm_logic" in pkg_name:
                gaps.append(
                    {
                        "type": "missing_test",
                        "target": node_id,
                        "priority": "MEDIUM",
                        "reason": f"Module {pkg_name} has no associated unit tests.",
                    }
                )

        # 2. Detecting Roadmap Items Needing Research (Phase 200+)
        # If a roadmap item is not marked [x] and doesn't have a clear code node
        roadmap_lines = self.roadmap_text.split("\n")
        in_advanced_section = False
        for line in roadmap_lines:
            if "## Phase 130" in line or "## Phase 200" in line:
                in_advanced_section = True

            if in_advanced_section and "- [ ]" in line:
                # Found an incomplete advanced task
                task_name = line.replace("- [ ]", "").strip()
                gaps.append(
                    {
                        "type": "research_needed",
                        "target": task_name,
                        "priority": "HIGH",
                        "reason": f"Roadmap item '{task_name}' requires technical research for  implementation.",
                    }
                )

        return gaps

    def suggest_next_mission(self) -> Dict[str, Any]:
        """Suggest the single most impactful next mission."""
        gaps = self.analyze()
        if not gaps:
            return {
                "suggestion": "No immediate gaps found. Proceed to next Roadmap phase."
            }

        # Prioritize based on Roadmap (stub)
        high_priority = [g for g in gaps if g.get("priority") == "HIGH"]
        top_gap = high_priority[0] if high_priority else gaps[0]

        if top_gap["type"] == "research_needed":
            return {
                "suggestion": f"Research: {top_gap['target']}",
                "impact": "Required for Phase 200/130 Advancement",
                "action": f"research_web: {top_gap['target']}",
            }

        return {
            "suggestion": f"Increase Verification: {top_gap['target']}",
            "impact": "Improves Reliability (Goal )",
            "action": f"Create tests for {top_gap['target']}",
        }


if __name__ == "__main__":
    import os

    # GOV-003: Use environment variables for path neutrality
    kg_json = os.environ.get("WARMLOGIC_KNOWLEDGE_GRAPH", "knowledge_graph.json")
    roadmap_md = os.environ.get("WARMLOGIC_ROADMAP", "AGI_10_10_ROADMAP.md")

    tasker = AutoTasker(kg_json, roadmap_md)
    suggestion = tasker.suggest_next_mission()

    print("Intelligence Report: Suggested Next Mission")
    print("-" * 40)
    print(f"Goal: {suggestion['suggestion']}")
    print(f"Impact: {suggestion['impact']}")
    print(f"Action: {suggestion['action']}")
