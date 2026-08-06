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
import ast
import logging
import os
from dataclasses import dataclass
from typing import List

logger = logging.getLogger("SovereignAuditor")


@dataclass
class LogicGap:
    file_path: str
    line_number: int
    description: str
    gap_type: str  # 'Stub', 'Complexity', 'TestDebt'
    priority: int = 1


class RecursiveDebtAuditor:
    """
    [M] The Recursive Eye.
    Autonomously discovers architectural and logical debt within the Sovereign Lattice.
    """

    def __init__(self, root_path: str):
        self.root_path = root_path

    def scan_all(self) -> List[LogicGap]:
        """
        Exhaustive scan for Logic Gaps.
        """
        gaps = []
        for root, _, files in os.walk(self.root_path):
            if ".venv" in root or "__pycache__" in root or ".git" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    gaps.extend(self.scan_file(path))

        logger.info(
            f"🕵️ [Discovery] Scan complete. Found {len(gaps)} potential improvements."
        )
        return gaps

    def scan_file(self, file_path: str) -> List[LogicGap]:
        """
        Analyzes a single file for debt.
        """
        gaps = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)

            # 1. Discovery: Stub Detection
            gaps.extend(self._find_stubs(tree, file_path))

            # 2. Discovery: Complexity Debt
            gaps.extend(self._analyze_complexity(tree, file_path))

        except Exception as e:
            logger.error(f"[Discovery] Failed to scan {file_path}: {e}")

        return gaps

    def _find_stubs(self, tree: ast.AST, file_path: str) -> List[LogicGap]:
        """
        Finds NotImplementedError or TODO markers.
        """
        stubs = []
        for node in ast.walk(tree):
            # NotImplementedError detection
            if isinstance(node, ast.Raise):
                if (
                    isinstance(node.exc, ast.Call)
                    and getattr(node.exc.func, "id", "") == "NotImplementedError"
                ):
                    stubs.append(
                        LogicGap(
                            file_path=file_path,
                            line_number=node.lineno,
                            description=f"Stub in {os.path.basename(file_path)}",
                            gap_type="Stub",
                            priority=2,
                        )
                    )

            # TODO detection in strings (docstrings/comments aren't in AST walk(tree) easily for comments)
            # But we can check for Expr statements containing strings
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str) and "TODO" in node.value.value:
                    stubs.append(
                        LogicGap(
                            file_path=file_path,
                            line_number=node.lineno,
                            description="TODO found in docstring/expression",
                            gap_type="Stub",
                            priority=1,
                        )
                    )
        return stubs

    def _analyze_complexity(self, tree: ast.AST, file_path: str) -> List[LogicGap]:
        """
        Crude cyclomatic complexity calculation.
        """
        complex_gaps = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = 0
                for subnode in ast.walk(node):
                    if isinstance(
                        subnode,
                        (
                            ast.If,
                            ast.While,
                            ast.For,
                            ast.AsyncFor,
                            ast.ExceptHandler,
                            ast.With,
                            ast.AsyncWith,
                        ),
                    ):
                        complexity += 1

                if complexity >= 10:
                    complex_gaps.append(
                        LogicGap(
                            file_path=file_path,
                            line_number=node.lineno,
                            description=f"High Complexity ({complexity}) in function '{node.name}'",
                            gap_type="Complexity",
                            priority=3,
                        )
                    )
        return complex_gaps
