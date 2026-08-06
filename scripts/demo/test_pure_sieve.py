"""
Pure Sieve Verification Test (Era 46).
Verifies that the runtime integrity validator detects tampering.
"""

import asyncio
import logging
import os
import sys

# Dynamic root detection
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from warm_logic.security.pure_sieve import PureSieve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PureSieveTest")


async def test_pure_sieve():
    print(" Starting Era 46 Pure Sieve Verification...")

    # Setup temp files for testing
    temp_dir = os.path.join(ROOT_DIR, "temp_sieve_test")
    os.makedirs(temp_dir, exist_ok=True)

    file1 = os.path.join(temp_dir, "core_logic.py")
    with open(file1, "w") as f:
        f.write("# Original Logic\ndef run(): print('Sovereign')")

    sieve = PureSieve(temp_dir)

    print("\n--- Phase 1: Baseline Generation ---")
    sieve.generate_baseline(["core_logic.py"])
    assert sieve.verify_runtime() is True
    print("Local baseline verified.")

    print("\n--- Phase 2: Detecting Tampering ---")
    print("Modifying core_logic.py (Simulating Host Compromise)...")
    with open(file1, "a") as f:
        f.write("\n# Malicious Injection")

    is_valid = sieve.verify_runtime()
    print(f"Result: Integrity Valid = {is_valid}")
    assert is_valid is False
    print("Tampering detected successfully.")

    print("\n--- Phase 3: Missing File Detection ---")
    print("Deleting core_logic.py...")
    os.remove(file1)
    is_valid = sieve.verify_runtime()
    print(f"Result: Integrity Valid = {is_valid}")
    assert is_valid is False
    print("Missing component detected successfully.")

    print("\nEra 46 Verification Passed: Runtime integrity is now enforceable.")

    # Cleanup
    if os.path.exists(temp_dir):
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)


if __name__ == "__main__":
    asyncio.run(test_pure_sieve())
