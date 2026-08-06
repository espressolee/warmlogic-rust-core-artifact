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

logger = logging.getLogger("SovereignCodex")


@dataclass(frozen=True)
class LogicGap:
    file_path: str
    line_number: int
    description: str
    gap_type: str  # "NotImplemented" or "TODO"
    priority: int = 50
    complexity: int = 1


class SovereignCodebase:
    """
    The Codex: A self-reflection engine for the Sovereign Codebase.
    Allows the kernel to read, analyze, and eventually repair its own source code.
    """

    def __init__(self, root_path: str = "."):
        self.root_path = os.path.abspath(root_path)
        self.ignore_dirs = {
            ".git",
            ".venv",
            "__pycache__",
            ".gemini",
            "node_modules",
            ".pytest_cache",
        }

    def scan_codebase(self) -> List[LogicGap]:
        """
        Scans the entire codebase for missing logic markers.
        Target markers:
        1. raise NotImplementedError
        2. # TODO comments
        """
        gaps = []
        logger.info(f"[convergence] Scanning codebase at {self.root_path}...")

        for root, dirs, files in os.walk(self.root_path):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    gaps.extend(self._analyze_file(full_path))

        logger.info(
            f"🧠 [convergence] Analysis complete. Found {len(gaps)} logic gaps."
        )
        return gaps

    def _analyze_file(self, file_path: str) -> List[LogicGap]:
        local_gaps = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            # 1. AST Analysis for NotImplementedError
            try:
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Raise):
                        exc = node.exc
                        if not exc:
                            continue

                        is_target = False

                        # Case 1: raise NotImplementedError
                        if (
                            isinstance(exc, ast.Name)
                            and exc.id == "NotImplementedError"
                        ):
                            is_target = True

                        # Case 2: raise NotImplementedError("msg")
                        elif (
                            isinstance(exc, ast.Call)
                            and isinstance(exc.func, ast.Name)
                            and exc.func.id == "NotImplementedError"
                        ):
                            is_target = True

                        if is_target:
                            msg = "Explicit NotImplementedError raised"
                            # Try to extract message
                            if isinstance(exc, ast.Call) and exc.args:
                                try:
                                    arg0 = exc.args[0]
                                    if isinstance(arg0, ast.Constant):
                                        msg = str(arg0.value)
                                    elif isinstance(arg0, ast.Str):
                                        msg = arg0.s
                                except Exception:
                                    pass

                            local_gaps.append(
                                LogicGap(
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    description=msg,
                                    gap_type="NotImplemented",
                                )
                            )
            except SyntaxError:
                logger.warning(f"[convergence] Failed to parse AST for {file_path}")

            # 2. Text Analysis for TODOs
            lines = source.splitlines()
            for idx, line in enumerate(lines):
                if "# TODO" in line or "# TODO:" in line:
                    local_gaps.append(
                        LogicGap(
                            file_path=file_path,
                            line_number=idx + 1,
                            description=line.strip(),
                            gap_type="TODO",
                        )
                    )

        except Exception as e:
            logger.error(f"[convergence] Read error on {file_path}: {e}")

        return local_gaps

    def propose_backfill(self, gap: LogicGap) -> str:
        """
        [Stub] Generates a prompt or plan to fill the gap.
        Future Era: Connects to LLM or internal heuristics.
        """
        return f"PLAN: Implement missing logic for {gap.gap_type} at {gap.file_path}:{gap.line_number}"
