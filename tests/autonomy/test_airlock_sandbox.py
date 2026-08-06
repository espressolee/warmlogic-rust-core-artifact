import time
import unittest

from warm_logic.kernel.autonomy.airlock import AirlockValidator


class TestAirlock(unittest.TestCase):
    def test_safe_logic(self):
        """Standard arithmetic should pass."""
        body = "x = 10 * 10"
        test = "assert x == 100"
        self.assertTrue(AirlockValidator.validate(body, test))

    def test_infinite_loop_timeout(self):
        """Infinite loop should be caught by timeout."""
        body = "while True: pass"
        test = "assert True"
        self.assertFalse(AirlockValidator.validate(body, test, timeout_sec=1.0))

    def test_system_exit(self):
        """Code that calls exit should fail."""
        body = "import sys; sys.exit(1)"
        test = "assert True"
        self.assertFalse(AirlockValidator.validate(body, test))

    def test_segfault_simulation(self):
        """Simulate a crash (import ctypes; ctypes.string_at(0)) if possible, or just exit 139."""
        # Hard to reliably segfault cross-platform without deps, so we simulate strict exit
        body = "import os; os._exit(1)"
        test = "assert True"
        self.assertFalse(AirlockValidator.validate(body, test))


if __name__ == "__main__":
    unittest.main()
