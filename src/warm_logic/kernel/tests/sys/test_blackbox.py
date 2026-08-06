# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import sys

# Force path
sys.path.append(os.getcwd())

from warm_logic.kernel.sys.blackbox import BlackBox


def test_blackbox_integrity():
    print("Starting BlackBox Integrity Verification...")

    test_ledger = "data/audit/test_ledger.jsonl"
    if os.path.exists(test_ledger):
        os.remove(test_ledger)

    # 1. Initialize and Log
    box = BlackBox(ledger_path=test_ledger)
    print("   -> Logging events...")
    box.log({"thought": "I think therefore I am"})
    box.log({"decision": "Upgrade Kernel"})
    box.log({"action": "rm -rf (just kidding)"})

    # 2. Verify Valid Chain
    print("   -> Verifying valid chain...")
    assert box.verify_integrity() == True

    # 3. Tamper (Modify line 2)
    print("   -> Attempting Tamper (Rewriting History)...")
    with open(test_ledger, "r") as f:
        lines = f.readlines()

    # Modify second entry content
    import json

    tampered_entry = json.loads(lines[1])
    tampered_entry["content"]["decision"] = "Upgrade Downgrade"  # Tamper
    # We keep hash same, so hash check fails.
    # Or if we recalc hash, prev_hash of next block fails.
    lines[1] = json.dumps(tampered_entry) + "\n"

    with open(test_ledger, "w") as f:
        f.writelines(lines)

    # 4. Verify Detection
    print("   -> Auditing Tampered Ledger...")
    assert box.verify_integrity() == False

    print("[Audit] Tamper successfully detected!")

    # Cleanup
    if os.path.exists(test_ledger):
        os.remove(test_ledger)


if __name__ == "__main__":
    test_blackbox_integrity()
