import os
import platform
import sys
from pathlib import Path

# Fix Path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print(f"Python Protocol: {sys.version}")
print(f" Platform: {platform.machine()}")

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError as e:
    print(f"Failed to import: {e}")
    sys.exit(1)


def run_sanity():
    print("Running Sanity Check (Sign)")
    try:
        # Generate Keypair
        pub, priv = warm_logic_rs.generate_keypair()
        print(f"Keypair Generated: {pub[:10]}...")

        # Sign
        sig = warm_logic_rs.sign(priv, "Hello World")
        print(f" Signature: {sig[:10]}...")
        print("Sanity Check Passed")
    except Exception as e:
        print(f"Sanity Check Failed: {e}")


if __name__ == "__main__":
    run_sanity()
