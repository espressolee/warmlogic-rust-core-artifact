#!/usr/bin/env bash
# OS v2 Audit Spine Demo
# Usage: ./os_v2_audit_spine_demo.sh

set -e

echo "[*] Setting up OS v2 Demo Environment..."
export PYTHONPATH=.
mkdir -p ledger
touch ledger/CE_Ledger_v1.jsonl

# 1. Create Synthetic Intents
echo "[*] Generating Intents..."
cat <<EOF > intent_valid.json
{
  "intent_id": "INT-001",
  "actor": {"id": "user-alice", "role": "admin"},
  "scope": {"org_id": "org-demo", "tenant_id": "t1"},
  "target": {"system": "payment-gateway", "resource": "limit", "action": "update"},
  "evidence_refs": ["proofs/witness_001.json"],
  "context": {"risk_class": "HIGH"}
}
EOF

cat <<EOF > intent_invalid.json
{
  "intent_id": "INT-002",
  "actor": {"id": "bot-auto", "role": "service"},
  "scope": {"org_id": "org-demo", "tenant_id": "t1"},
  "target": {"system": "payment-gateway", "resource": "limit", "action": "update"},
  "evidence_refs": [],
  "context": {"risk_class": "HIGH"}
}
EOF

# 2. Run Kernel via simple python script wrapper
echo "[*] Initializing Kernel Wrapper..."
cat <<EOF > run_kernel.py
import json
import sys
from src.os_v2.kernel.loop import kernel
from src.os_v2.integration.audit_spine_adapter import spine_adapter

def run(file_path):
    with open(file_path) as f:
        intent = json.load(f)

    print(f"--- Processing {file_path} ---")
    decision = kernel.execute(intent)
    print(f"Decision: {decision['decision']}")

    bundle_path = spine_adapter.process_decision(decision, intent)
    print(f"Bundle: {bundle_path}")

if __name__ == "__main__":
    run(sys.argv[1])
EOF

# 3. Execute
echo "[*] Executing Valid Intent..."
python3 run_kernel.py intent_valid.json

echo "[*] Executing Invalid Intent..."
python3 run_kernel.py intent_invalid.json

# 4. Verify
echo ""
echo "[*] Verifying Output..."
ls -R out/audit_spine/
echo ""
echo "[*] CE Ledger Content:"
cat ledger/CE_Ledger_v1.jsonl | tail -n 2

echo "[SUCCESS] OS v2 Demo Complete."
