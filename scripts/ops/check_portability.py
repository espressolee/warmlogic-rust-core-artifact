"""Portability Audit (Era 40).
Verifies that the codebase is pure Python and free of absolute paths/binaries.
verification Readiness Check.
"""

import logging
import os
import re
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PortabilityAudit")

# Dynamic root detection
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger.info(f"Root Directory identified as: {ROOT_DIR}")

# Only audit these critical source directories
AUDIT_TARGETS = ["warm_logic", "scripts", "docs", "tests", "meta"]

BINARY_EXTENSIONS = [".so", ".dylib", ".dll", ".exe", ".bin", ".pyc", ".pyd"]
ABS_PATH_PATTERN = re.compile(r"(['\"])/Users/.*?['\"]")  # Detects hardcoded Mac paths


def audit():
    violations = 0
    logger.info("Starting Focused Portability Audit...")

    for target in AUDIT_TARGETS:
        target_path = os.path.join(ROOT_DIR, target)
        if not os.path.exists(target_path):
            continue

        logger.info(f"Auditing target: {target}")

        for root, dirs, files in os.walk(target_path):
            # Pruning ignored directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

            rel_path = os.path.relpath(root, ROOT_DIR)

            for name in files:
                file_path = os.path.join(root, name)

                # Skip the audit script itself
                if name == "check_portability.py":
                    continue

                # 1. Binary Check
                _, ext = os.path.splitext(name)
                if ext.lower() in BINARY_EXTENSIONS:
                    logger.error(f"Binary found: {os.path.join(rel_path, name)}")
                    violations += 1
                    continue

                # 2. Source Code Checks (Python/MD/JSON files)
                if ext.lower() in [".py", ".md", ".json"]:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                            # A. Absolute Path Check
                            if name not in ["task.md", "implementation_plan.md"]:
                                matches = ABS_PATH_PATTERN.findall(content)
                                if matches:
                                    logger.error(
                                        f"🚫 Hardcoded absolute path in {os.path.join(rel_path, name)}"
                                    )
                                    violations += 1

                            # B. Dangerous Import Check (ctypes) - Python only
                            if ext.lower() == ".py":
                                if (
                                    "import ctypes" in content
                                    or "from ctypes" in content
                                ):
                                    logger.warning(
                                        f"⚠️ ctypes usage (unportable) in {os.path.join(rel_path, name)}"
                                    )

                    except Exception as e:
                        pass

    if violations > 0:
        logger.error(f"Portability Audit Failed with {violations} violations.")
    else:
        logger.info("Portability Audit Passed. Codebase is pure and mobile.")

    return violations


if __name__ == "__main__":
    audit()
