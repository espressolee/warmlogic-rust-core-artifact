#!/usr/bin/env python3
import os
import sys


def main():
    print("WARMLOGIC WORKSPACE HYGIENE CHECKER")
    print("=" * 50)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "../.."))  # WarmLogic root

    allowed_dirs = {
        "warm_logic",
        "warm_logic_rs_crate",
        "docs",
        "spec",
        "scripts",  # Allowed for audit/devloop tools
        "out",  # Sometimes present (forbidden items often checks contents or specific bans)
        "config",
        "pov-kit",  # Legacy/Support
        "archives",
        "artifacts",
        "warm_logic.egg-info",
        "venv",
        ".venv",
        ".git",
        ".agent",
        ".gemini",
        ".idea",
        ".vscode",
        "__pycache__",
        "meta",
        "ledger",
    }
    allowed_files = {
        "README.md",
        "README_v2.md",
        "LICENSE",
        ".DS_Store",
        "pyproject.toml",
        "pytest.ini",
        "justfile",
        "Makefile",
        "CODEOWNERS",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "GENESIS_MANIFESTO.md",
        "WL_PROGRAM_PROGRESS_CHECKLIST_v1.0.md",
        "Dockerfile",
        "Dockerfile.sovereign",
        "docker-compose.yml",
        "conftest.py",
        "WarmLogic.code-workspace",
        "battle_scars.log",
        "__init__.py",
        "SOVEREIGN_BASELINE.json",
    }

    forbidden_items = {"model", "data"}  # Critical violations

    problems = []
    warnings = []
    critical_violations = []

    items = sorted(os.listdir(repo_root))

    for item in items:
        if item.startswith("."):  # Ignore most dotfiles for now
            if item not in allowed_dirs and item not in allowed_files:
                # Hidden files get a light warning but aren't grounds for failure unless explicitly forbidden
                continue

        path = os.path.join(repo_root, item)
        is_dir = os.path.isdir(path)

        if item in forbidden_items:
            critical_violations.append(f"❌ FORBIDDEN: Found '{item}' at root level.")
            continue

        if is_dir:
            if item not in allowed_dirs:
                warnings.append(f"⚠️ UNEXPECTED DIR: '{item}'")
        else:
            if item not in allowed_files:
                warnings.append(f"⚠️ UNEXPECTED FILE: '{item}'")

    if critical_violations:
        for v in critical_violations:
            print(v)
        print("\nVERDICT: HYGIENE CRITICALLY VIOLATED")
        sys.exit(1)

    if warnings:
        for w in warnings:
            print(w)
        print("\nVERDICT: HYGIENE SUB-OPTIMAL (Warnings only)")
        sys.exit(2)

    print("VERDICT: HYGIENE PERFECT")
    sys.exit(0)


if __name__ == "__main__":
    main()
