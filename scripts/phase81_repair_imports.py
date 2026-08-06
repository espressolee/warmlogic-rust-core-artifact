import os
import re
from pathlib import Path

ROOT = Path("./")

# Order matters! Specific paths first, then general catch-alls.
REPLACEMENTS = {
    # =========================================================================
    # PHASE 88: UNIVERSAL SINGULARITY
    # =========================================================================
    # Flattened Kernel (All sub-packages -> kernel root)
    r"warm_logic\.kernel\.(base|ops|sys|ai|logic)\.": "warm_logic.kernel.",
    # Specific Module Merges (Legacy)
    r"warm_logic\.kernel\.ai\.attention_flow": "warm_logic.kernel.brain",
    r"warm_logic\.kernel\.ai\.(director|proprioception|meta_policy_ml)": "warm_logic.kernel.brain",
    r"warm_logic\.kernel\.logic\.formal_runtime": "warm_logic.kernel.foundation",
    r"warm_logic\.kernel\.logic\.formal_invariants": "warm_logic.kernel.foundation",
    r"warm_logic\.kernel\.logic\.fsm": "warm_logic.kernel.foundation",
    # Dashboard & App
    r"warm_logic\.app\.dashboard\.\w+": "warm_logic.app.dashboard.dashboard",
    # Catch-all for internal root moves
    r"from warm_logic\.kernel\.(base|ops|sys|ai|logic) import": "from warm_logic.kernel import",
}


def fix_imports():
    print("Starting Phase 85.1 Mass Import Repair...")
    count = 0

    # Iterate ALL files
    targets = list(ROOT.rglob("*.py"))

    for f in targets:
        if "venv" in str(f) or "node_modules" in str(f):
            continue

        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue

        new_content = content
        modified = False

        for pat, repl in REPLACEMENTS.items():
            if re.search(pat, new_content):
                new_content = re.sub(pat, repl, new_content)
                modified = True

        if modified:
            f.write_text(new_content, encoding="utf-8")
            count += 1

    print(f"Fixed imports in {count} files.")


if __name__ == "__main__":
    fix_imports()
