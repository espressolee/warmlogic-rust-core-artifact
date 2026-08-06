"""
Doc Path Relativizer (Era 46 Audit).
Lists all absolute paths in the docs for final purification.
"""

import os
import re

ROOT_DIR = "./"
DOCS_DIR = os.path.join(ROOT_DIR, "docs")

pattern = re.compile(r"./([^ \)]+)")


def find_absolute_paths():
    found = False
    for root, _, files in os.walk(DOCS_DIR):
        for f in files:
            if f.endswith(".md"):
                path = os.path.join(root, f)
                with open(path, "r") as file_handle:
                    content = file_handle.read()
                    matches = pattern.findall(content)
                    if matches:
                        print(
                            f"📄 {os.path.relpath(path, ROOT_DIR)}: {len(matches)} absolute paths found."
                        )
                        found = True
    if not found:
        print("No absolute paths found in /docs.")


if __name__ == "__main__":
    find_absolute_paths()
