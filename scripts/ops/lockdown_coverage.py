#!/usr/bin/env python3
import os
import shutil
import sys
import unittest
from io import StringIO

import coverage

# Configuration: File -> Required Coverage %
LOCKDOWN_TARGETS = {
    "warm_logic/kernel/ops/metrics.py": 100,
    "warm_logic/kernel/ops/policy.py": 100,
    "warm_logic/kernel/ops/audit.py": 100,
    "warm_logic/kernel/base/protocol.py": 100,
    "warm_logic/kernel/base/wasm.py": 100,
    "warm_logic/kernel/sys/patch_engine.py": 100,
    "warm_logic/kernel/substrate/proof_generator.py": 100,
}


def run_lockdown():
    print("running Civilizational Lockdown (Coverage Enforcement)...")

    # 1. Initialize
    cov = coverage.Coverage(
        source=["warm_logic/kernel"], branch=True, omit=["*/tests/*", "*/__init__.py"]
    )
    cov.start()

    # 2. Run Tests
    loader = unittest.TestLoader()
    start_dir = os.path.abspath("warm_logic/kernel/tests")
    cache_dir = os.path.join(start_dir, ".pytest_cache")
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

    suite = loader.discover(start_dir, pattern="test_*.py", top_level_dir=os.getcwd())
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    cov.stop()
    cov.save()

    if not result.wasSuccessful():
        print("Tests FAILED. Lockdown Aborted.")
        sys.exit(1)

    # 3. Analyze Data
    data = cov.get_data()
    failed = False

    print("\nLOCKDOWN STATUS:")
    print("-" * 140)
    print(f"{'File':<50} {'Score':<8} {'Target':<8} {'Misses / Partial Branches'}")
    print("-" * 140)

    for filename in sorted(data.measured_files()):
        rel_path = os.path.relpath(filename, os.getcwd())

        # Check if this file is a target
        target = next(
            (v for k, v in LOCKDOWN_TARGETS.items() if rel_path.endswith(k)), None
        )
        target_name = next(
            (k for k, v in LOCKDOWN_TARGETS.items() if rel_path.endswith(k)), rel_path
        )

        if not target:
            continue

        # Capture standard report to find the specific file line
        buf = StringIO()
        actual_cov = cov.report(morfs=[filename], file=buf, show_missing=True)
        report_lines = buf.getvalue().strip().split("\n")

        # Header (2 lines) + File data (1 line) + Total line (1 line)
        # We find the line that contains the filename
        file_report = "???"
        for line in report_lines:
            if rel_path in line or (target_name and target_name in line):
                file_report = line
                break

        flag = "✅"
        msg = ""
        if actual_cov < target:
            flag = "❌"
            failed = True
            # Extract the 'Missing' column (the last part of the line)
            parts = file_report.split()
            if len(parts) > 6:
                msg = f" >> {parts[-1]}"

        print(f"{target_name:<50} {actual_cov:.1f}%    {target}% {flag}{msg}")

    print("-" * 140)
    if failed:
        print("LOCKDOWN VIOLATION: Coverage below targets.")
        sys.exit(1)
    else:
        print("CIVILIZATIONAL LOCKDOWN: SECURE.")
        sys.exit(0)


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    run_lockdown()
