#!/usr/bin/env python3
import hashlib
import json
import time
from pathlib import Path


def generate_shadow_witness():
    print("Initializing the Shadow Witness (Agent-Independent Trust)...")

    audit_reports = list(Path("out/audit").glob("*.json"))
    witness_log = []

    for report_path in audit_reports:
        with open(report_path, "rb") as f:
            report_hash = hashlib.sha256(f.read()).hexdigest()

        witness_log.append(
            {
                "target": report_path.name,
                "shadow_hash": report_hash,
                "witness_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        print(f"   Witnessed: {report_path.name} -> {report_hash[:16]}...")

    # Save Shadow Witness Ledger
    out_path = Path("out/security/shadow_witness_ledger.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(witness_log, f, indent=2)

    print(f"Shadow Witness Ledger sealed at {out_path}")
    print(
        "   This ledger must be compared against the agent-generated reports for total finality."
    )


if __name__ == "__main__":
    generate_shadow_witness()
