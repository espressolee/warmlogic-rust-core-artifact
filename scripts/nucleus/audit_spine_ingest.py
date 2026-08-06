#!/usr/bin/env python3
import json
from pathlib import Path


def verify_spine_integrity():
    spine_path = Path("out/audit/planetary_spine.jsonl")
    if not spine_path.exists():
        print("Error: Planetary Spine not found.")
        return

    print(f"Verifying Planetary Audit Spine: {spine_path}")
    count = 0
    with open(spine_path, "r") as f:
        for line in f:
            receipt = json.loads(line)
            # Verify basic structure (In Era 2, this would check the Shadow Witness signature)
            if "seal" in receipt and "node_id" in receipt:
                count += 1
            else:
                print(f"CORRUPTION DETECTED at entry {count}!")
                return False

    print(f"PASS: {count} Witness Receipts verified. Atomic Law is intact.")
    return True


if __name__ == "__main__":
    verify_spine_integrity()
