""" Evidence Bundle Verification
Tests the packaging and signing of forensic artifacts.
"""

import shutil
import sys
import zipfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.justice.audit_ledger import AuditLedger
from warm_logic.kernel.justice.evidence_packager import EvidencePackager


def test_evidence():
    print("Testing Evidence Packager...")

    # 0. Ensure some data exists
    AuditLedger().record_event("TEST_EVENT", {"note": "Generating Evidence"})

    # 1. Run Packager
    packager = EvidencePackager()
    zip_path, sig_path = packager.collect_and_package()

    print(f"Generated: {zip_path.name}")

    # 2. Verify Files Exist
    if not zip_path.exists() or not sig_path.exists():
        print("Files missing.")
        sys.exit(1)

    # 3. Verify Zip Integrity
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            print(f"   Contents: {names}")

            required = ["ledger.jsonl", "REPORT.md", "identity.pub"]
            for req in required:
                if req not in names:
                    print(f"Missing required file in zip: {req}")
                    sys.exit(1)

            # Read identity to verify
            pub_key = zf.read("identity.pub").decode().strip()
            print(f"   Identity: {pub_key[:16]}...")

    except zipfile.BadZipFile:
        print("Invalid Zip File.")
        sys.exit(1)

    # 4. Cleanup
    shutil.rmtree(packager.output_dir)
    print("Cleanup complete.")

    print("\nEVIDENCE BUNDLE SCENARIO OK (not verification)")


if __name__ == "__main__":
    test_evidence()
