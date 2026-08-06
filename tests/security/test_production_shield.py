import unittest

from warm_logic.kernel.sys.shield import SyscallShield, SyscallViolation


class TestProductionShield(unittest.TestCase):
    def setUp(self):
        self.shield = SyscallShield(agent_profile="restricted")

    def test_rust_guard_active(self):
        self.assertIsNotNone(self.shield.rust_guard)
        self.assertEqual(self.shield.rust_guard.violations, 0)

    def test_memory_boundary_violation(self):
        # 1MB limit for restricted profile write syscall in our implementation
        safe_data = "A" * 1024
        self.shield.enforce("write", (1, safe_data))  # Should pass

        huge_data = "B" * (1024 * 1024 + 1)
        with self.assertRaises(SyscallViolation) as cm:
            self.shield.enforce("write", (1, huge_data))

        self.assertIn("Memory Boundary Violation", str(cm.exception))
        self.assertEqual(self.shield.rust_guard.violations, 1)

    def test_secret_protection(self):
        # Test protect_secret directly (internal check)
        self.assertTrue(
            self.shield.rust_guard.protect_secret(
                "valid_secret_long_enough_for_32_chars_12345"
            )
        )
        self.assertFalse(self.shield.rust_guard.protect_secret("short"))
        self.assertEqual(self.shield.rust_guard.violations, 1)  # Incremented by 'short'


if __name__ == "__main__":
    unittest.main()
