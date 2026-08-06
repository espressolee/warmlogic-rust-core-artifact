import os
import subprocess
import sys

# Force absolute root and sanitize path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
while root in sys.path:
    sys.path.remove(root)
sys.path.insert(0, root)


def run_all_tests():
    print(" Sovereign Runner: Initiating Mass Execution via Surgical Subprocess ...")
    print(f"[ROOT] {root}")

    # --- ENVIRONMENT HEALTH CHECK ---
    try:
        import warm_logic.kernel

        print("Environment check: warm_logic.kernel is importable.")
        import warm_logic as warm_logic_core

        print(
            f"✅ Environment check: warm_logic_core alias established ({warm_logic_core.__name__})"
        )
    except ImportError as e:
        print(f"Environment check failed: {e}")
        return

    test_dirs = [
        "warm_logic/kernel/tests/system",
        "warm_logic/kernel/tests/justice",
        "warm_logic/kernel/tests/economy",
    ]

    test_files = []
    for td in test_dirs:
        dir_path = os.path.join(root, td)
        if os.path.exists(dir_path):
            for r, d, f in os.walk(dir_path):
                for file in f:
                    if file.startswith("test_") and file.endswith(".py"):
                        test_files.append(os.path.join(r, file))

    print(f"Found {len(test_files)} potential test files.")

    # --- SANDBOX EXECUTION ---
    sandbox = "/tmp/sovereign_sandbox"
    if os.path.exists(sandbox):
        import shutil

        try:
            shutil.rmtree(sandbox)
        except Exception:
            # Fallback if rmtree fails due to system locks
            subprocess.run(["rm", "-rf", sandbox])
    os.makedirs(sandbox)

    print(f" Building sandbox in {sandbox} ...")
    # Use rsync to skip problematic hidden files and __pycache__
    rsync_cmd = [
        "rsync",
        "-av",
        "--exclude",
        ".*",
        "--exclude",
        "__pycache__",
        os.path.join(root, "warm_logic/"),
        os.path.join(sandbox, "warm_logic"),
    ]
    subprocess.run(
        rsync_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )

    pytest_path = "pytest"
    coverage_file = os.path.abspath(os.path.join(root, ".coverage_sovereign"))

    cmd = [
        pytest_path,
        "-v",
        "--cov",
        "warm_logic.kernel",
        "--cov-report",
        "term-missing",
        "warm_logic/kernel/tests/system",
        "warm_logic/kernel/tests/justice",
        "warm_logic/kernel/tests/economy",
    ]

    print(f"Executing Pytest in Sandbox: {' '.join(cmd)}")
    # Run in sandbox with sandbox as PYTHONPATH
    result = subprocess.run(
        cmd,
        cwd=sandbox,
        env={**os.environ, "PYTHONPATH": sandbox, "COVERAGE_FILE": coverage_file},
    )

    if result.returncode == 0:
        print("All tests passed!")
    elif result.returncode == 5:
        print(" No tests found in sandbox. Check copy logic.")
    else:
        print(f" Tests failed with code {result.returncode}")


if __name__ == "__main__":
    run_all_tests()
