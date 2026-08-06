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
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set


class KnowledgeGraph:
    """
    Scans the WarmLogic codebase to build a graph of relationships
    between implementation (src), verification (tests), and goals (docs).
    """

    def __init__(self, root_dir: str) -> None:
        self.root_dir = Path(root_dir)
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, str]] = []

    SKIPPED_DIRS = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".agent",
        ".gemini",
    }

    def scan(self) -> None:
        """Perform a full scan of the project."""
        self._scan_src()
        self._scan_tests()
        self._scan_docs()
        self._correlate()

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        for part in path.parts:
            if part in self.SKIPPED_DIRS:
                return True
        return False

    def _scan_src(self) -> None:
        """Scan src directory for modules and their dependencies."""
        src_path = self.root_dir / "src"
        if not src_path.exists():
            return

        for py_file in src_path.rglob("*.py"):
            if self._should_skip(py_file):
                continue

            rel_path = str(py_file.relative_to(self.root_dir))
            node_id = f"src:{rel_path}"

            imports = self._get_imports(py_file)

            self.nodes[node_id] = {
                "type": "code",
                "path": rel_path,
                "imports": list(imports),
                "loc": self._safe_loc(py_file),
            }

            for imp in imports:
                if "warm_logic" in imp:
                    self.edges.append(
                        {"from": node_id, "to": f"imp:{imp}", "type": "dependency"}
                    )

    def _safe_loc(self, path: Path) -> int:
        """Safely count lines of code."""
        try:
            with open(path, "rb") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _scan_tests(self) -> None:
        """Scan tests directory and link to src."""
        tests_path = self.root_dir / "tests"
        if not tests_path.exists():
            return

        for py_file in tests_path.rglob("test_*.py"):
            if self._should_skip(py_file):
                continue

            rel_path = str(py_file.relative_to(self.root_dir))
            node_id = f"test:{rel_path}"

            imports = self._get_imports(py_file)

            self.nodes[node_id] = {
                "type": "test",
                "path": rel_path,
                "target_pkg": [imp for imp in imports if "warm_logic" in imp],
            }

            for pkg in self.nodes[node_id]["target_pkg"]:
                self.edges.append({"from": node_id, "to": pkg, "type": "verification"})

    def _scan_docs(self) -> None:
        """Scan docs and markdown files for goals/roadmap references."""
        for md_file in self.root_dir.rglob("*.md"):
            if self._should_skip(md_file):
                continue

            rel_path = str(md_file.relative_to(self.root_dir))
            node_id = f"doc:{rel_path}"

            try:
                content = md_file.read_text(errors="ignore")
                # Extract mentions of files or phases
                mentions = []
                if "Phase" in content:
                    import re

                    mentions = re.findall(r"Phase \d+", content)

                self.nodes[node_id] = {
                    "type": "documentation",
                    "path": rel_path,
                    "mentions": mentions,
                }
            except Exception:
                pass

    def _get_imports(self, file_path: Path) -> Set[str]:
        """Extract python imports using AST."""
        imports = set()
        try:
            tree = ast.parse(file_path.read_text(errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imports.add(n.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
        except Exception:
            pass
        return imports

    def _correlate(self) -> None:
        """Correlate nodes to find orphans or gaps."""
        # TODO: Advanced correlation logic
        pass

    def save(self, output_path: str) -> None:
        """Save the graph to JSON."""
        data = {"nodes": self.nodes, "edges": self.edges}
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)


if __name__ == "__main__":
    import os

    # GOV-003: Use environment variable or current directory for path neutrality
    root_dir = os.environ.get("WARMLOGIC_ROOT", ".")
    kg = KnowledgeGraph(root_dir)
    kg.scan()
    output = os.path.join(root_dir, "knowledge_graph.json")
    kg.save(output)
    print(f"Knowledge Graph saved to {output}")
    print(f"Nodes: {len(kg.nodes)}, Edges: {len(kg.edges)}")
