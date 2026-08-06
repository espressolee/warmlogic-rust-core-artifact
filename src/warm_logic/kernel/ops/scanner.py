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
from typing import Dict, Any, List
import libcst as cst
from pathlib import Path

logger = logging.getLogger("ASTScanner")


class ComplexityVisitor(cst.CSTVisitor):
    def __init__(self) -> None:
        self.complexity = 1
        self.max_nesting = 0
        self.current_nesting = 0

    def visit_If(self, node: cst.If) -> None:
        self.complexity += 1
        self._enter_nesting()

    def leave_If(self, node: cst.If) -> None:
        self._leave_nesting()

    def visit_For(self, node: cst.For) -> None:
        self.complexity += 1
        self._enter_nesting()

    def leave_For(self, node: cst.For) -> None:
        self._leave_nesting()

    def visit_While(self, node: cst.While) -> None:
        self.complexity += 1
        self._enter_nesting()

    def leave_While(self, node: cst.While) -> None:
        self._leave_nesting()

    def _enter_nesting(self) -> None:
        self.current_nesting += 1
        self.max_nesting = max(self.max_nesting, self.current_nesting)

    def _leave_nesting(self) -> None:
        self.current_nesting -= 1


class ASTScanner:
    """
    The Structural Scanner.
    Analyzes code structure using Concrete Syntax Trees.
    """

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found"}

        try:
            source = path.read_text()
            tree = cst.parse_module(source)

            visitor = ComplexityVisitor()
            tree.visit(visitor)

            return {
                "complexity": visitor.complexity,
                "max_nesting": visitor.max_nesting,
                "loc": len(source.splitlines()),
            }
        except Exception as e:
            logger.error(f"Failed to scan {file_path}: {e}")
            return {"error": str(e)}

    def detect_structural_gaps(self, file_path: str) -> List[Dict[str, Any]]:
        metrics = self.analyze_file(file_path)
        gaps = []

        if metrics.get("error"):
            return []

        # Heuristics for "Spaghetti Code"
        if metrics.get("complexity", 0) > 10:
            gaps.append(
                {
                    "type": "HIGH_COMPLEXITY",
                    "severity": float(metrics["complexity"]) / 10.0,
                    "rel_path": file_path,
                    "reason": f"Cyclomatic complexity {metrics['complexity']} is too high.",
                }
            )

        if metrics.get("max_nesting", 0) >= 4:
            gaps.append(
                {
                    "type": "DEEP_NESTING",
                    "severity": float(metrics["max_nesting"]) / 4.0,
                    "rel_path": file_path,
                    "reason": f"Nesting depth {metrics['max_nesting']} exceeds limit of 3.",
                }
            )

        return gaps
