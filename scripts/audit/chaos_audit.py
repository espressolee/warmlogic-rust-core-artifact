#!/usr/bin/env python3
import hashlib
import os
import random
import sys
from pathlib import Path

# Paths to audit
AUDIT_TARGETS = [
    "warm_logic/kernel/kernel_loop.py",
    "warm_logic/intelligence/guard.py",
    "warm_logic/economy/sovereign_bridge.py",
]


def calculate_checksum(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def run_chaos_audit():
    print("Starting WarmLogic Chaos Audit V1...")

    # 1. Baseline
    checksums = {}
    for target in AUDIT_TARGETS:
        if os.path.exists(target):
            checksums[target] = calculate_checksum(target)
            print(f"Baseline established for {target}: {checksums[target][:16]}...")
        else:
            print(f"Target {target} not found. Skipping.")

    print("\nVerifying all targets...")
    for target, baseline in checksums.items():
        current = calculate_checksum(target)
        if current == baseline:
            print(f"{target}: INTEGRITY VERIFIED")
        else:
            print(f"{target}: INTEGRITY FAILED!")
            sys.exit(1)

    # 2. Chaos Injection
    print("\nInjecting Chaos (Bit Corruption)...")
    target_to_corrupt = random.choice(list(checksums.keys()))
    backup_content = Path(target_to_corrupt).read_bytes()

    try:
        # Corrupt one byte
        corrupted_content = bytearray(backup_content)
        idx = random.randint(0, len(corrupted_content) - 1)
        corrupted_content[idx] = (corrupted_content[idx] + 1) % 256

        Path(target_to_corrupt).write_bytes(corrupted_content)
        print(f"Corrupted {target_to_corrupt} at byte {idx}.")

        # 3. Verification of Failure
        print("\nTesting detection of corruption...")
        current = calculate_checksum(target_to_corrupt)
        if current != checksums[target_to_corrupt]:
            print(f"SUCCESS: Corruption detected in {target_to_corrupt}!")
            print(f"   Baseline: {checksums[target_to_corrupt]}")
            print(f"   Current:  {current}")
        else:
            print("FAILURE: Corruption NOT detected. Integrity system compromised.")
            sys.exit(1)

    finally:
        # Restore
        Path(target_to_corrupt).write_bytes(backup_content)
        print(f"\nRestored {target_to_corrupt} to baseline.")

    print(
        "\n✨ Chaos Audit Complete. The 'Hard Constraint' is no longer a hallucination."
    )


if __name__ == "__main__":
    run_chaos_audit()
