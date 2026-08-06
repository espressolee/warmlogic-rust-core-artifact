"""Purify Workspace (Era 40).
Cleans up the project root by moving non-critical files to archives.
Also deep-cleans subdirectories of trash.
"""

import logging
import os
import re
import shutil
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Purification")

# Dynamic Root Determination
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARCHIVE_MISC = os.path.join(ROOT_DIR, "archives/misc")

# Critical paths that MUST stay at root
STAY_LIST = [
    "warm_logic",
    "docs",
    "scripts",
    "ledger",
    "legacy_archive",
    "meta",
    "tests",
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "Makefile",
    "justfile",
    "Dockerfile",
    "docker-compose.yml",
    "config",
    "archives",
    "warm_logic.db",
    ".git",
    ".gitignore",
    ".agent",
]

TRASH_PATTERNS = [r".* \d+$", r"^__pycache__$", r"^\.DS_Store$"]


def deep_clean():
    """Recursively removes pycache and shadow dirs in the whole project."""
    logger.info("Deep cleaning subdirectories...")
    for root, dirs, files in os.walk(ROOT_DIR):
        # Don't clean archives itself too much or .git
        if ".git" in root or "archives" in root:
            continue

        for d in list(dirs):
            if d == "__pycache__" or any(
                re.match(p, d) for p in TRASH_PATTERNS if p != r"^\.DS_Store$"
            ):
                dir_path = os.path.join(root, d)
                logger.info(f"Deleting shadow/pycache dir: {dir_path}")
                shutil.rmtree(dir_path)
                dirs.remove(d)

        for f in files:
            if f == ".DS_Store" or f.endswith(".pyc") or f.endswith(".bin"):
                file_path = os.path.join(root, f)
                # Skip legacy_archive as those might be intentional (though Era 40 says pure Python)
                if "legacy_archive" in file_path:
                    continue
                logger.info(f"Deleting trash file: {file_path}")
                os.remove(file_path)


def purify(dry_run: bool = False):
    if not os.path.exists(ARCHIVE_MISC):
        os.makedirs(ARCHIVE_MISC, exist_ok=True)

    items = os.listdir(ROOT_DIR)
    moved_count = 0

    for item in items:
        # Skip critical items
        if item in STAY_LIST:
            continue

        # Skip hidden files
        if item.startswith("."):
            continue

        src_path = os.path.join(ROOT_DIR, item)
        dst_path = os.path.join(ARCHIVE_MISC, item)

        if dry_run:
            logger.info(f"[Dry Run] Would move: {item} -> archives/misc/")
            moved_count += 1
        else:
            try:
                # Handle collisions
                if os.path.exists(dst_path):
                    if os.path.isdir(dst_path):
                        shutil.rmtree(dst_path)
                    else:
                        os.remove(dst_path)

                shutil.move(src_path, dst_path)
                logger.info(f"Moved: {item} -> archives/misc/")
                moved_count += 1
            except Exception as e:
                logger.error(f"Failed to move {item}: {e}")

    if not dry_run:
        deep_clean()

    logger.info(f"Purification finished. Total items moved: {moved_count}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    purify(dry_run=dry_run)
