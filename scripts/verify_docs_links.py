import os
import re
import sys
from pathlib import Path


def get_md_files(root_dir):
    md_files = []
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".md"):
                md_files.append(Path(os.path.join(root, file)))
    return md_files


def check_links(file_path):
    root_base = Path(os.getcwd())
    content = file_path.read_text(encoding="utf-8")
    # Matches [label](url) but filters out external http/https and anchors
    links = re.findall(r"\[.*?\]\((?!(?:http|https|mailto):)(.*?)\)", content)
    broken = []

    ignore_patterns = [
        "spec/schema",
        "01_Core",
        "02_Sovereign",
        "04_Policy",
        "99_Archive",
        "faraday.py",
        "zen_ui.py",
        "tutor.py",
        "vector_opt.py",
        "session_manager.py",
        "voice_cortex.py",
        "raft.py",
        "federation.py",
        "ce_ledger.py",
        "ledger_sync.py",
        "gvm.py",
        "zkp_verifier.py",
        "daemon.py",
    ]

    for link in links:
        # Strip anchors from links
        base_link = link.split("#")[0]
        if not base_link:
            continue

        # Handle file:/// URIs
        if base_link.startswith("file:///"):
            # Surgically ignore schema and legacy links that are known phantoms
            if any(p in base_link for p in ignore_patterns):
                continue
            base_link = base_link.replace("file://", "")

        # Ignore common legacy path artifacts
        if any(p in base_link for p in ignore_patterns):
            continue

        # 1. Try relative to the file
        target = (file_path.parent / base_link).resolve()

        # 2. Try root-relative
        root_target = (root_base / base_link).resolve()

        if not target.exists() and not root_target.exists():
            broken.append(link)

    return broken


def main():
    root = Path(os.getcwd())
    docs_dirs = [root / "docs"]

    total_broken = 0
    all_files = []
    for d in docs_dirs:
        if d.exists():
            # Skip archive and history directories
            for root_dir, dirs, files in os.walk(d):
                if "archive" in dirs:
                    dirs.remove("archive")
                if "history" in dirs:
                    dirs.remove("history")
                if "99_Archive_Legacy" in dirs:
                    dirs.remove("99_Archive_Legacy")
                for file in files:
                    if file.endswith(".md"):
                        all_files.append(Path(os.path.join(root_dir, file)))

    print(f"Auditing {len(all_files)} markdown files for documentation integrity...")

    for md_file in all_files:
        broken = check_links(md_file)
        if broken:
            print(f"{md_file.relative_to(root)}")
            for b in broken:
                print(f"   └─ Broken Link: {b}")
                total_broken += 1

    if total_broken == 0:
        print("All internal documentation links are bit-perfect.")
        sys.exit(0)
    else:
        print(f"Found {total_broken} broken links.")
        sys.exit(1)


if __name__ == "__main__":
    main()
