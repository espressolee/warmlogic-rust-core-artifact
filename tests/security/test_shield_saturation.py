import sys
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.shield import (
    SyscallShield,
    SyscallViolation,
    kernel_exec,
    kernel_open,
    kernel_socket,
    shield_syscall,
)


class TestShieldSaturation:
    def test_init_rust_import_error(self):
        """Test SyscallShield initialization when warm_logic_rs is missing."""
        with patch.dict(sys.modules, {"warm_logic_rs": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                shield = SyscallShield()
                assert shield.rust_guard is None

    def test_init_rust_success(self):
        """Test SyscallShield initialization when warm_logic_rs is present."""
        mock_guard_class = MagicMock()
        with patch.dict(
            sys.modules, {"warm_logic_rs": MagicMock(ShieldGuard=mock_guard_class)}
        ):
            shield = SyscallShield()
            assert shield.rust_guard is not None
            mock_guard_class.assert_called_once()

    def test_enforce_rust_boundary_violation(self):
        """Test memory boundary violation enforced by Rust guard."""
        shield = SyscallShield()
        shield.rust_guard = MagicMock()
        # verify_boundary(start, len, max) -> False
        shield.rust_guard.verify_boundary.return_value = False

        with pytest.raises(SyscallViolation, match="Memory Boundary Violation"):
            shield.enforce("write", (1, "very long data", 100))

    def test_enforce_blocked_panic(self):
        """Test blocked syscall with panic=True."""
        shield = SyscallShield()
        shield.policies["restricted"]["blocked"].add("kill")
        shield.policies["restricted"]["panic"] = True

        with pytest.raises(SyscallViolation, match="violated profile 'restricted'"):
            shield.enforce("kill")

    def test_enforce_blocked_no_panic(self):
        """Test blocked syscall with panic=False."""
        shield = SyscallShield()
        shield.policies["restricted"]["blocked"] = {"kill"}
        shield.policies["restricted"]["panic"] = False

        assert shield.enforce("kill") is False

    def test_enforce_not_allowed_panic(self):
        """Test syscall not in allow-list with panic=True."""
        shield = SyscallShield()
        shield.policies["restricted"]["allowed"] = {"read"}  # open is blocked
        shield.policies["restricted"]["panic"] = True

        with pytest.raises(SyscallViolation, match="not in allow-list"):
            shield.enforce("open")

    def test_enforce_not_allowed_no_panic(self):
        """Test syscall not in allow-list with panic=False."""
        shield = SyscallShield()
        shield.policies["restricted"]["allowed"] = {"read"}
        shield.policies["restricted"]["panic"] = False

        assert shield.enforce("open") is False

    def test_profile_fallback(self):
        """Test fallback to restricted profile for unknown profiles."""
        shield = SyscallShield(agent_profile="unknown_ghost")
        # Should use restricted policy
        assert shield._get_active_policy() == shield.policies["restricted"]
        assert shield.enforce("read") is True

    def test_shield_syscall_decorator(self):
        """Verify the @shield_syscall decorator logic."""
        shield_instance = SyscallShield()

        @shield_syscall("read")
        def mocked_read(data):
            return f"Read: {data}"

        # Should pass
        with patch("warm_logic.kernel.sys.shield.shield", shield_instance):
            assert mocked_read("info") == "Read: info"

        # Should block if we change policy
        shield_instance.policies["restricted"]["allowed"] = set()
        with patch("warm_logic.kernel.sys.shield.shield", shield_instance):
            with pytest.raises(SyscallViolation):
                mocked_read("info")

    def test_kernel_barriers_unimplemented(self):
        """Test that kernel barriers trigger RuntimeError when allowed by policy but unimplemented."""
        shield_instance = SyscallShield(agent_profile="unlocked")
        # Custom profile that allows everything
        shield_instance.policies["unlocked"] = {
            "allowed": {"*"},
            "blocked": set(),
            "panic": False,
        }

        with patch("warm_logic.kernel.sys.shield.shield", shield_instance):
            # Now these should bypass the shield but hit the function's RuntimeError
            with pytest.raises(RuntimeError, match="No real 'execve' syscall"):
                kernel_exec("/bin/sh", ("/bin/sh",))

            with pytest.raises(RuntimeError, match="No real 'socket' syscall"):
                kernel_socket(1, 1)

    def test_kernel_barriers_panic(self):
        """Test that kernel barriers trigger SyscallViolation then RuntimeError."""
        # By default 'open' is allowed, but 'execve' and 'socket' are blocked
        shield_instance = SyscallShield()

        with patch("warm_logic.kernel.sys.shield.shield", shield_instance):
            # 1. Blocked syscall (execve) -> SyscallViolation
            with pytest.raises(SyscallViolation, match="execve"):
                kernel_exec("/bin/sh", ("/bin/sh",))

            # 2. Blocked syscall (socket) -> SyscallViolation
            with pytest.raises(SyscallViolation, match="socket"):
                kernel_socket(1, 1)

            # 3. Allowed but unimplemented (open) -> RuntimeError
            with pytest.raises(RuntimeError, match="No real 'open' syscall"):
                kernel_open("/etc/passwd", 0)

    def test_syscall_violation_exception(self):
        """Simple coverage for the SyscallViolation class itself."""
        e = SyscallViolation("test")
        assert str(e) == "test"
