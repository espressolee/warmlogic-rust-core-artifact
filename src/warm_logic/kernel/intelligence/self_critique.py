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
from pathlib import Path


class SelfCritique:
    """
    Evaluates Recent Work (implementation_plan, walkthrough, code changes)
    against the "Brutal Perfection" standard.
    """

    def __init__(self, walkthrough_path: str):
        self.walkthrough_path = Path(walkthrough_path)

    def evaluate(self, src_dir: str = "src"):
        """Perform a harsh evaluation of current project status by scanning source code."""
        src_path = Path(src_dir)
        critiques = []

        trigger_keywords = ["disabl", "hack", "temporary", "placeholder", "partial"]
        found_triggers = []

        # 1. Scan Source Files
        if src_path.exists():
            for py_file in src_path.rglob("*.py"):
                # Skip intelligence tools themselves to avoid self-recursion triggers
                if "intelligence" in str(py_file):
                    continue

                try:
                    content = py_file.read_text(errors="ignore").lower()
                    for kw in trigger_keywords:
                        if kw in content:
                            found_triggers.append(f"{py_file.name} ({kw})")
                except Exception:
                    continue

        # 2. Heuristic: Detect "Disabled" features as potential hacks
        if found_triggers:
            # Deduplicate and format
            trigger_summary = ", ".join(list(set(found_triggers))[:5])
            critiques.append(
                {
                    "severity": "HIGH",
                    "finding": f"Technical Debt/Hacks Detected in Source: {trigger_summary}",
                    "recommmendation": "Refactor these components into formal models or remove temporary deactivations. No shortcuts in a  system.",
                }
            )

        return critiques

    def generate_report(self):
        findings = self.evaluate()
        if not findings:
            return "Self-Critique: No major flaws detected. System is progressing toward ."

        report = "Self-Critique Report: Brutal Truth\n"
        report += "=" * 40 + "\n"
        for f in findings:
            report += f"[{f['severity']}] {f['finding']}\n"
            report += f"  - Action: {f['recommmendation']}\n"
        return report


if __name__ == "__main__":
    import os

    # GOV-003: Use environment variable for path neutrality
    w_path = os.environ.get("WARMLOGIC_WALKTHROUGH", "walkthrough.md")
    sc = SelfCritique(w_path)
    print(sc.generate_report())
