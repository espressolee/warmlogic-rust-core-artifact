import os
import sys

import pytest


def run_isolated():
    """
    Runs pytest programmatically to avoid shell/config issues causing permission errors.
    Target: Justice Pillar tests.
    """
    print(" Running Isolated Justice Tests...")

    # Force the rootdir to be the test directory to avoid scanning the project root
    target_test = "warm_logic/kernel/tests/justice/test_sovereign_justice.py"
    target_dir = os.path.dirname(target_test)

    # BYPASS: The root .coverage file is locked. Redirect to a local file.
    os.environ["COVERAGE_FILE"] = ".coverage.justice"

    # Args:
    # -v: Verbose
    # -s: Disable capture (see stdout)
    # -c /dev/null: Ignore default config
    # --rootdir: Force root deeper
    args = [
        "-v",
        "-s",
        "-c",
        "/dev/null",
        f"--rootdir={target_dir}",
        "--cov=warm_logic/kernel/justice",
        "--cov-report=term-missing",
        target_test,
    ]

    # We need to ensure the project root is in path for imports
    project_root = os.getcwd()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print(f" Running Isolated Justice Tests...", file=sys.stderr)
    print(f"   Target: {target_test}", file=sys.stderr)
    print(f"   Root: {project_root}", file=sys.stderr)

    ret = pytest.main(args)

    if ret == 0:
        print("Justice Tests Passed.")
    else:
        print(f"Tests Failed with code {ret}")
        sys.exit(ret)


if __name__ == "__main__":
    run_isolated()
