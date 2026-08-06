#!/usr/bin/env python3
import os
import unittest

import coverage


def global_audit():
    print("GLOBAL COVERAGE AUDIT: WARMLOGIC KERNEL")
    print("-" * 60)

    cov = coverage.Coverage(
        source=["warm_logic/kernel"], branch=True, omit=["*/tests/*", "*/__init__.py"]
    )
    cov.start()

    loader = unittest.TestLoader()
    suite = loader.discover(
        "warm_logic/kernel/tests", pattern="test_*.py", top_level_dir=os.getcwd()
    )
    unittest.TextTestRunner(verbosity=0).run(suite)

    cov.stop()
    cov.save()

    print("\nCURRENT STATUS:")
    cov.report(show_missing=False)


if __name__ == "__main__":
    global_audit()
