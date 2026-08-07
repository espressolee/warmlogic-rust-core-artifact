#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys


def get_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Verify Brand Archive integrity.")
    parser.add_argument(
        "--rebase",
        action="store_true",
        help="Update manifest with current hashes and remove missing files.",
    )
    args = parser.parse_args()

    print("WARMLOGIC BRAND ARCHIVE VERIFIER")
    print("=" * 50)

    # Paths are relative to the script's location or REPO_ROOT
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "../../.."))  # Resonance root
    archive_root = os.path.join(repo_root, "Brand Archive")
    manifest_path = os.path.join(archive_root, "Brand Archive MD/ARCHIVE_MANIFEST.json")

    if not os.path.exists(manifest_path):
        print(f"ERROR: Manifest not found at {manifest_path}")
        sys.exit(1)

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    files = manifest.get("files", [])
    new_files = []

    matched = 0
    mismatched = 0
    missing = 0
    ignored = 0

    print(
        f"📦 Manifest version: {manifest.get('doc_version')} ({manifest.get('standard_version')})"
    )
    # The original line `print(f"Scanning {total_files} files...")` is removed.

    for file_entry in files:
        rel_path = file_entry.get("path")
        # The original line `expected_hash_full = file_entry.get("hash")  # e.g. "sha256:..."` is moved and modified.
        if not rel_path:
            continue

        # Ignore __pycache__ and other transient artifacts
        if "__pycache__" in rel_path or rel_path.endswith(".pyc"):
            ignored += 1
            if not args.rebase:
                continue
            else:
                # If rebasing, we skip adding this to the new manifest
                continue

        full_path = os.path.join(archive_root, rel_path)
        expected_hash_full = file_entry.get("hash", "")
        expected_hash = expected_hash_full.split(":")[-1]

        if not os.path.exists(full_path):
            print(f"  MISSING: {rel_path}")
            missing += 1
            if args.rebase:
                continue  # Do not include in new manifest
            new_files.append(file_entry)
            continue

        actual_hash = get_sha256(full_path)
        if actual_hash == expected_hash:
            matched += 1
            new_files.append(file_entry)
        else:
            print(f"  MISMATCH: {rel_path}")
            # The original print lines for expected/actual hash are removed.
            mismatched += 1
            if args.rebase:
                file_entry["hash"] = f"sha256:{actual_hash}"
                print(f"    -> Rebased to: {actual_hash}")
            new_files.append(file_entry)

    print("=" * 50)
    print(f"Matched:    {matched}")
    if mismatched > 0:
        print(f"Mismatched: {mismatched}")
    if missing > 0:
        print(f"Missing:    {missing}")
    if ignored > 0:
        print(f"Ignored:    {ignored} (transient)")

    if args.rebase:
        manifest["files"] = new_files
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)
        print("\nREBASE COMPLETE: Manifest updated.")
        sys.exit(0)

    if mismatched == 0 and missing == 0:
        print(
            "\n🏆 VERDICT: ARCHIVE INTEGRITY SCENARIO OK (not verification)"
        )  # The original "(100% MATCH)" is removed.
        sys.exit(0)
    else:
        print("\nVERDICT: ARCHIVE INTEGRITY COMPROMISED")
        sys.exit(1)


if __name__ == "__main__":
    main()
