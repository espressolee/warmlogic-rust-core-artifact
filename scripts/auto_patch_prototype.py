import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup simple logging
logging.basicConfig(level=logging.INFO)

from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.patcher import AutonomousPatcher


async def run_patch_cycle():
    print("[Auto-Patch] Initializing Autonomous Patcher...")
    target_file = PROJECT_ROOT / "warm_logic/chaos/broken_module.py"

    if not target_file.exists():
        print(f"Target {target_file} not found.")
        return

    patcher = AutonomousPatcher(root_path=str(PROJECT_ROOT))

    # Dynamic detection to match AST exactly
    import ast

    with open(target_file, "r") as f:
        tree = ast.parse(f.read())

    target_lineno = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            # Just take the first one for the test
            target_lineno = node.lineno
            break

    if target_lineno is None:
        print("Could not find Raise node for test setup.")
        return

    gap = LogicGap(
        file_path=str(target_file),
        line_number=target_lineno,
        description="Critical logic missing in critical_function",
        gap_type="NotImplemented",
        priority=100,
    )

    print(f"[Auto-Patch] Detected LogicGap: {gap.description}")
    print("[Auto-Patch] Applying STUB strategy...")

    success = await patcher.apply_patch(gap, strategy="stub")

    if success:
        print("[Auto-Patch] Patch applied successfully.")

        # Verification: Read the file back
        with open(target_file, "r") as f:
            content = f.read()
        print("\n[Patched Content Preview]:")
        print("-" * 40)
        print(content)
        print("-" * 40)

        # Verify functionality (should not raise anymore)
        try:
            # Dynamic import to test
            import importlib.util

            spec = importlib.util.spec_from_file_location("broken_module", target_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            print("[Auto-Patch] Running patched function...")
            module.critical_function()
            print("[Auto-Patch] Function ran without crashing!")

        except ImportError:
            print("Import failed.")
        except Exception as e:
            print(f"Function still crashed: {e}")

    else:
        print("[Auto-Patch] Patch failed.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_patch_cycle())
