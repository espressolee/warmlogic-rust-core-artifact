""" closure Evolution Verification
Tests the "Quine Loop" - ensuring the system can modify itself and persist the change.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.ops.omega_daemon import ClosureDaemon
from warm_logic.kernel.sys.patch_engine import PatchEngine


def test_evolution():
    print("Testing closure Evolution (Self-Modification)...")

    root = Path(__file__).parent.parent.resolve()
    omega = ClosureDaemon(root)

    # 1. Setup a Test Subject
    subject_rel = "warm_logic/kernel/sys/patch_engine.py"
    subject_abs = root / subject_rel

    # [Fix] Reset to known clean state to prevent "Method already exists" errors
    clean_code = '''"""
Patch Engine
Provides safe, AST-based self-modification capabilities for the WarmLogic Kernel.
"""

import ast
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("PatchEngine")

class PatchEngine:
    """
    Applies AST transformations to Python source files.
    Ensures syntax validity before writing to disk.
    """

    @staticmethod
    def inject_method(target_path: Path, class_name: str, method_code: str) -> bool:
        """
        Injects a method into a class.

        Args:
            target_path: Path to the python file.
            class_name: Name of the class to modify.
            method_code: Source code of the method to inject.
        """
        try:
            source = target_path.read_text()
            tree = ast.parse(source)
            new_method_ast = ast.parse(method_code).body[0]

            if not isinstance(new_method_ast, ast.FunctionDef):
                logger.error("Provided code is not a valid function definition.")
                return False

            class_found = False
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    # check if method already exists
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == new_method_ast.name:
                            logger.warning(f"Method {new_method_ast.name} already exists in {class_name}.")
                            return False

                    node.body.append(new_method_ast)
                    class_found = True
                    break

            if not class_found:
                logger.error(f"Class {class_name} not found in {target_path}.")
                return False

            # Verify validity by converting back to source (using ast.unparse if avail, or naive approach)
            if hasattr(ast, "unparse"):
                new_source = ast.unparse(tree)
            else:
                logger.warning("Using ast.unparse - comments may be lost during evolution.")
                new_source = ast.unparse(tree)

            target_path.write_text(new_source)
            return True

        except Exception as e:
            logger.error(f"Patch failed: {e}")
            return False
'''
    with open(subject_abs, "w") as f:
        f.write(clean_code)

    # Ensure subject is monitored (Pardoned)
    omega.pardon_file(subject_rel)
    print(f"Pardoned {subject_rel}")

    # 2. Define Mutation
    # We will inject a harmless method 'verify_evolution' into PatchEngine class
    # [Fix] Dedent the code block for AST parsing
    def evolve_logic(path: Path) -> bool:
        # Strip leading newline if present and ensure correct indentation for Class-level injection?
        # PatchEngine.inject_method parses `code` as a standalone snippet.
        # It expects a FunctionDef.
        # The AST parser is sensitive to indentation if it looks like it belongs inside something.
        # But if we parse "def foo(): ...", it should be fine.
        # Use explicit newline character in a way that survives python parsing
        # simple string concat is safer than escaping hell
        code_sanitized = (
            "def verify_evolution(self) -> str:\n    return 'I have evolved.'"
        )
        return PatchEngine.inject_method(path, "PatchEngine", code_sanitized)

    # 3. Attempt Unauthorized Mutation (Should be Reverted)
    print("\n--- Test 1: Unauthorized Mutation (Simulating Corruption) ---")
    with open(subject_abs, "a") as f:
        f.write("\n# CORRUPTION\n")

    violations = omega.scan_and_enforce()
    if violations > 0:
        print(f"closure correctly reverted {violations} unauthorized change(s).")
    else:
        print("closure FAILED to detect unauthorized change.")
        sys.exit(1)

    # 4. Attempt Authorized Mutation (The Quine Loop)
    print("\n--- Test 2: Authorized Mutation (Evolution) ---")
    success = omega.approve_mutation(subject_rel, evolve_logic)

    if success:
        print("Mutation Approved and Applied.")
    else:
        print("Evolution Failed.")
        sys.exit(1)

    # 5. Verify Persistence
    # Run scan again. closure should NOT revert this change because it was re-pardoned.
    violations = omega.scan_and_enforce()
    if violations == 0:
        print("closure accepted the Evolution (No Reversion).")
    else:
        print("closure REVERTED the Evolution! (Pardon failed).")
        sys.exit(1)

    # 6. Verify Code Logic
    # Check if the new method actually exists in the class
    # Need to reload module to see changes or parse file
    with open(subject_abs, "r") as f:
        content = f.read()
        if "def verify_evolution(self)" in content:
            print("Code successfully injected on disk.")
        else:
            print("Injected code not found on disk.")
            sys.exit(1)

    print("\nCLOSURE EVOLUTION SCENARIO OK (not verification)")


if __name__ == "__main__":
    test_evolution()
