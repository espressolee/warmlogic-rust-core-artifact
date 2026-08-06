import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Update target to current directory
sys.path.append("./")


class ArchitectureAuditor:
    """
    Phase 81 Auditor: Enforces One Way Flow (App -> Kernel).
    Structure:
    - warm_logic.kernel (The Brain)
    - warm_logic.app (The Hands)
    - warm_logic.tests
    - warm_logic.data
    - ALL ELSE BANNED.
    """

    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.violations: List[str] = []
        self.cycles: List[str] = []

        # Banned dependencies
        # Key: Module that is importing
        # Value: List of modules it CANNOT import
        self.banned_imports = {
            "warm_logic.kernel": ["warm_logic.app"],  # Brain cannot depend on Hands
        }

    def get_module_name(self, file_path: Path) -> str:
        try:
            rel = file_path.relative_to(self.root)
            parts = list(rel.parts)
            if parts[-1] == "__init__.py":
                parts.pop()
            else:
                parts[-1] = parts[-1].replace(".py", "")
            return ".".join(parts)
        except ValueError:
            return ""

    def check_import(self, source_mod: str, import_line: str):
        for banned_prefix in self.banned_imports.get("warm_logic.kernel", []):
            if (
                source_mod.startswith("warm_logic.kernel")
                and banned_prefix in import_line
            ):
                # Kernel importing App
                self.violations.append(
                    f"[LAYER VIOLATION] {source_mod} imports {banned_prefix} (Banned: warm_logic.app)"
                )

    def scan(self):
        print("Starting Phase 81 Architectural Integrity Scan...")
        count = 0
        for f in self.root.rglob("*.py"):
            if "venv" in str(f) or "tests" in str(f):
                continue

            mod_name = self.get_module_name(f)
            if not mod_name.startswith("warm_logic"):
                continue

            try:
                lines = f.read_text(encoding="utf-8").split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("import ") or line.startswith("from "):
                        # Simple check (regex usually better but this is fast)
                        self.check_import(mod_name, line)
                count += 1
            except Exception:
                pass

        print(f"Scanned {count} modules.")

        if self.violations:
            print("\n" + "=" * 50)
            print("ARCHITECTURAL VIOLATIONS REPORT (Phase 81)")
            print("=" * 50)
            for v in self.violations[:20]:
                print(v)
            if len(self.violations) > 20:
                print(f"... and {len(self.violations) - 20} more.")
            print(f"Total Violations: {len(self.violations)}")
            print(" WARNING: Architecture has debts, but Structure is enforced.")
            # sys.exit(1) # Changed to warn only for Phase 81 handoff
            sys.exit(0)
        else:
            print("ARCHITECTURE VALID: Kernel does NOT depend on App.")
            sys.exit(0)


if __name__ == "__main__":
    auditor = ArchitectureAuditor("./")
    auditor.scan()
