import sys
from pathlib import Path
from warm_logic.system.replication.codebase import SovereignCodebase
from warm_logic.kernel.sys.persistence import SovereignStore

print(f"CWD: {Path.cwd()}")
try:
    store = SovereignStore("test_debug.db")
    codebase = SovereignCodebase(store)
    count = codebase.ingest("warm_logic/system")
    print(f"Ingested count: {count}")
except Exception as e:
    print(f"Error: {e}")
