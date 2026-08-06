import os
import shutil

import warm_logic_rs

DB_PATH = "sovereign_db_test"
if os.path.exists(DB_PATH):
    shutil.rmtree(DB_PATH)

print("Initializing Store...")
try:
    store = warm_logic_rs.SovereignStore(DB_PATH)
    print("Store Initialized.")

    print("Putting data...")
    store.put("test_key", "test_value")
    print("Data Put.")

    print("Getting data...")
    val = store.get("test_key")
    print(f"Got: {val}")

    # Clean up
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

    print("Done.")
except Exception as e:
    print(f"CRASH/ERROR: {e}")
