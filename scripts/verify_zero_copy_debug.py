import sys
import time
from pathlib import Path

# Fix Path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError:
    print("Failed to import warm_logic_rs")
    sys.exit(1)


def run_debug():
    print("Starting Debug with 1KB (PyBytes)")
    data = bytes(1024)
    res = warm_logic_rs.benchmark_zero_copy(data)
    print(f"Result: {res}")


if __name__ == "__main__":
    run_debug()
