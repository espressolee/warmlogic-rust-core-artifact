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
import logging
import os
import shutil
import sys

# Force path
sys.path.append(os.getcwd())

from warm_logic.kernel.memory.vector_vault import VectorVault

logging.basicConfig(level=logging.INFO)


def test_persistence_recall():
    print("Starting Phase 67: Long-Term Memory Verification...")

    # 0. Clean Setup
    test_db_path = "data/memory/test_vector_store"
    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)

    # 1. Initialize First Session
    print("   -> [Session 1] Initializing Vector Memory...")
    vault = VectorVault(persist_path=test_db_path)

    # 2. Store Measurements
    print(
        "   -> [Session 1] Encoding Experience: 'Optimization of Kinetic Kernel succeeded'"
    )
    vault.store_thought(
        "Optimization of Kinetic Kernel succeeded with 50% speedup",
        {"module": "kernel", "success": True},
    )

    # 3. Simulate Restart (Re-initialize Vault at same path)
    del vault
    print("   -> [System Restart] Re-loading Memory Banks...")
    vault_v2 = VectorVault(persist_path=test_db_path)

    # 4. Recall
    query = "performance improvement"
    print(f"   -> [Session 2] Querying: '{query}'")
    results = vault_v2.query_thoughts(query, n_results=1)

    print(f"   -> Retrieved: {results}")

    # 5. Verify Semantics
    assert len(results) > 0
    assert "Optimization" in results[0]
    assert "50%" in results[0]

    print("\n[Phase 67] Long-Term Memory Verified!")
    print("   -> Persistence across restarts confirmed.")
    print("   -> Semantic recall confirmed.")

    # Cleanup
    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)


if __name__ == "__main__":
    test_persistence_recall()
