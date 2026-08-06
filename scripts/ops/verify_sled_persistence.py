import os
import shutil
from pathlib import Path

from warm_logic.kernel.sys.persistence import SovereignStore


def test_rust_persistence():
    dbg_path = Path("./test_sled_db")
    if dbg_path.exists():
        shutil.rmtree(dbg_path)

    os.makedirs(dbg_path)
    db_file = dbg_path / "test.db"

    print("Initializing SovereignStore (Targeting Sled)...")
    store = SovereignStore(db_file)

    if store._use_rust:
        print("Rust Core Detected and Active.")

        print("Testing Metadata (KV)...")
        store.set_meta("system_version", "1.0.0-PRO")
        ver = store.get_meta("system_version")
        print(f"   Retrieved Version: {ver}")
        assert ver == "1.0.0-PRO"

        print("Testing Balances...")
        bal = store.get_balance("espressolee")
        print(f"   Initial Balance (espressolee): {bal}")

        print("Testing Block Retrieval (initial)...")
        block = store.get_last_block()
        print(f"   Last Block: {block}")

        store.close()
        print("Test Passed.")
    else:
        print("Rust Core NOT Detected. Test skipped (requires Metal Persistence).")


if __name__ == "__main__":
    try:
        test_rust_persistence()
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback

        traceback.print_exc()
