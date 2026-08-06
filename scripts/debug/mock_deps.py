import os
import sys
from unittest.mock import MagicMock

# 1. Mock prometheus_client
mock_prom = MagicMock()
sys.modules["prometheus_client"] = mock_prom

# 2. Mock warm_logic_rs (if not already present)
# We can reuse the file we created, or just mock it here if that file isn't picked up
if "warm_logic_rs" not in sys.modules:
    # Try to import the local file
    try:
        import warm_logic_rs
    except ImportError:
        # Fallback to MagicMock if file missing
        mock_rs = MagicMock()
        mock_rs.RustZKProofGenerator.return_value.generate_state_proof.return_value.commitment_hex = "mock_commit"
        mock_rs.RustZKProofGenerator.return_value.generate_state_proof.return_value.proof_hex = "mock_proof_valid"
        mock_rs.RustZKProofGenerator.return_value.verify_state_proof.return_value = True
        sys.modules["warm_logic_rs"] = mock_rs

# 3. Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


# 4. Helper to run a script
def run_script(script_path):
    import runpy

    runpy.run_path(script_path, run_name="__main__")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 mock_deps.py <script_to_run> [args]")
        sys.exit(1)

    script = sys.argv[1]
    # Forward args
    sys.argv = [script] + sys.argv[2:]
    run_script(script)
