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
import importlib
import hashlib
import logging
import os
import sys
from unittest.mock import MagicMock

from unittest.mock import patch

from warm_logic.kernel.ops.propagation import SovereignPropagator
from warm_logic.kernel.sys.persistence import SovereignStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestPropagation")


def _resolve_codebase_class():
    root = os.getcwd()
    if root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)

    for module_name in ("dominion.replication.codebase", "dominion.replication", "dominion"):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("dominion.replication.codebase")
    module_file = os.path.abspath(getattr(module, "__file__", ""))
    expected_prefix = os.path.abspath(os.path.join(root, "dominion"))
    if not module_file.startswith(expected_prefix):
        raise RuntimeError(f"Unexpected codebase module resolved: {module_file}")
    return module.SovereignCodebase


@patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False)
def test_propagation_workflow():
    print("Starting propagation Verification...")
    SovereignCodebase = _resolve_codebase_class()

    # 1. Setup Primary Node
    store_a = SovereignStore(db_path="test_codebase_a.db")
    codebase_a = SovereignCodebase(store_a)
    mesh_a = MagicMock()
    mesh_a.node_id = "node_A"
    propagator_a = SovereignPropagator(codebase_a, mesh_a)

    # Ingest some dummy files
    test_file = "warm_logic/kernel/substrate/hardware.py"
    content_v1 = b"print('Hardware v1')"
    codebase_a._manifest[test_file] = codebase_a.store_blob(content_v1)

    # 2. Setup Peer Node (Node B)
    store_b = SovereignStore(db_path="test_codebase_b.db")
    codebase_b = SovereignCodebase(store_b)
    mesh_b = MagicMock()
    mesh_b.node_id = "node_B"
    propagator_b = SovereignPropagator(codebase_b, mesh_b)

    # Node B starts with the same state
    codebase_b._manifest[test_file] = codebase_b.store_blob(content_v1)

    # 3. Simulate Mutation on Node A (committed via BFT)
    print("Simulating BFT Commit on Node A...")
    content_v2 = b"print('Hardware v2 - EVOLVED')"
    hash_v2 = hashlib.sha256(content_v2).hexdigest()

    # Update Node A's store and manifest
    codebase_a.store_blob(content_v2)
    codebase_a._manifest[test_file] = hash_v2

    # 4. Generate and Receive Sync Signal
    print("Node A broadcasting SYNC_MANIFEST...")
    sync_signal = propagator_a.generate_sync_signal()

    # 5. Node B Processing
    print("Node B receiving SYNC_MANIFEST...")
    remote_hash = sync_signal["root_hash"]
    local_manifest = codebase_b.generate_manifest()

    assert local_manifest["root_hash"] != remote_hash
    print("Node B detected divergence. Syncing Delta...")

    # Identify Deltas
    delta = codebase_b.get_node_delta(sync_signal["files"])
    assert test_file in delta
    assert delta[test_file] == hash_v2
    print(f"Delta identified: {test_file} needs update to {hash_v2[:8]}")

    # 6. Blob Transfer (Simulation)
    # In a real network, Node B would request the blob from A.
    # Here, we simulate the 'receipt' of the blob by putting it into Node B's store.
    blob_v2 = codebase_a.get_blob(hash_v2)
    codebase_b.store_blob(blob_v2)  # "Received" the blob

    # 7. Apply Patch
    os.makedirs("node_b_env/warm_logic/kernel/substrate", exist_ok=True)
    success = codebase_b.apply_blob_patch(test_file, hash_v2, root_path="node_b_env")

    assert success
    assert codebase_b._manifest[test_file] == hash_v2

    # Verify file Content on Node B's pseudo-disk
    with open(f"node_b_env/{test_file}", "rb") as f:
        disk_content = f.read()
    assert disk_content == content_v2

    print("Node B successfully synced to convergence.")
    print("propagation Verification Successful!")

    # Cleanup
    import shutil

    # Small delay for Sled to release locks if needed
    store_a = None
    store_b = None
    import time

    time.sleep(0.5)

    if os.path.exists("test_codebase_a.db"):
        if os.path.isdir("test_codebase_a.db"):
            shutil.rmtree("test_codebase_a.db")
        else:
            os.remove("test_codebase_a.db")
    if os.path.exists("test_codebase_b.db"):
        if os.path.isdir("test_codebase_b.db"):
            shutil.rmtree("test_codebase_b.db")
        else:
            os.remove("test_codebase_b.db")
    # Also check the 'sled_db_...' prefix folders
    for d in os.listdir("."):
        if d.startswith("sled_db_test_codebase"):
            shutil.rmtree(d)
    if os.path.exists("node_b_env"):
        shutil.rmtree("node_b_env")


if __name__ == "__main__":
    try:
        test_propagation_workflow()
    except Exception as e:
        print(f"Verification Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
