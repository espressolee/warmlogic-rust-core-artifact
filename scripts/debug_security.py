import os
import sys
import unittest

# Ensure src and root are in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

# Inject mock
try:
    import warm_logic_rs_mock

    sys.modules["warm_logic_rs"] = warm_logic_rs_mock
    print("[Debug] Injected warm_logic_rs mock.")
except ImportError:
    print("[Debug] Could not inject warm_logic_rs mock.")

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover("tests/security", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        print("Security Tests FAILED")
        sys.exit(1)
    print("Security Tests PASSED")
