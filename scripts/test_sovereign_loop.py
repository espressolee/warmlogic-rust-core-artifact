""" Sovereign Loop Verification
Tests the Integration of Justice Pillars into the Living Kernel Loop.
"""

import shutil
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.bootloader import SovereignBootloader
from warm_logic.kernel.justice.audit_ledger import AuditLedger


def test_sovereign_loop():
    print("Testing Sovereign Loop Integration...")

    # 1. Setup
    root_dir = Path("warm_logic/kernel")
    # Clean previous forensic state for clean test
    sovereign_dir = Path(".sovereign")
    if sovereign_dir.exists():
        shutil.rmtree(sovereign_dir)

    # 2. Ignite Bootloader
    print("Igniting Bootloader...")
    boot = SovereignBootloader(
        str(root_dir), "warm_logic/_legacy"
    )  # Dummy archive path

    # Mock Heritage Integrity check?
    # Bootloader checks internal vault.
    # HeritageVault usually checks hashes.
    # Since we are running in dev, we hope it passes or we might need to mock verify_integrity.

    # Let's monkeypatch verify_integrity just in case, to focus on Loop integration
    boot.vault.verify_integrity = (
        lambda x: True
    )  # Bypass DNA check for this integration test

    loop = boot.ignite()

    # 3. Verify Context Injection
    print("Verifying Context Synapses...")
    ctx = loop.ctx

    if not ctx.audit_ledger:
        print("Audit Ledger NOT injected.")
        sys.exit(1)
    if not ctx.refusal_engine:
        print("Refusal Engine NOT injected.")
        sys.exit(1)
    if not ctx.snapshot_engine:
        print("Snapshot Engine NOT injected.")
        sys.exit(1)

    print("Justice Pillars injected successfully.")

    # 4. Trigger Ticks (Heartbeat Logging)
    print("Running 105 Ticks (Triggering Heartbeat)...")
    for _ in range(105):
        loop.tick()

    # 5. Verify Ledger
    print("Inspecting Audit Ledger...")
    with open(ctx.audit_ledger.ledger_path, "r") as f:
        log_content = f.read()

    # Check for BOOT_SEQUENCE (from ignite)
    if "BOOT_SEQUENCE" not in log_content:
        print("Ledger missing BOOT_SEQUENCE.")
        sys.exit(1)

    # Check for HEARTBEAT (from tick 100)
    if "HEARTBEAT" not in log_content:
        print("Ledger missing HEARTBEAT event (Tick 100).")
        sys.exit(1)

    print("Ledger recorded Boot and Heartbeat events.")
    print("\nSOVEREIGN LOOP VERIFIED")


if __name__ == "__main__":
    test_sovereign_loop()
