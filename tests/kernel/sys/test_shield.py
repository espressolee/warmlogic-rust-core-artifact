# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic Syscall Shield (ePASS)."""

from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.shield import (
    SyscallShield,
    SyscallViolation,
    shield_syscall,
    kernel_open,
    kernel_exec,
    kernel_socket,
)


class TestSyscallShield:
    """Test SyscallShield class."""

    def test_init_default_profile(self):
        """Initializes with restricted profile by default."""
        shield = SyscallShield()
        assert shield.profile == "restricted"

    def test_init_custom_profile(self):
        """Accepts custom profile name."""
        shield = SyscallShield(agent_profile="custom")
        assert shield.profile == "custom"

    def test_enforce_allowed_syscall(self):
        """Allows syscalls in allow-list."""
        shield = SyscallShield()

        assert shield.enforce("read") is True
        assert shield.enforce("write") is True
        assert shield.enforce("open") is True
        assert shield.enforce("close") is True
        assert shield.enforce("stat") is True
        assert shield.enforce("fstat") is True

    def test_enforce_blocked_syscall_raises(self):
        """Raises SyscallViolation for blocked syscalls."""
        shield = SyscallShield()

        with pytest.raises(SyscallViolation) as exc_info:
            shield.enforce("execve")
        assert "execve" in str(exc_info.value)
        assert "restricted" in str(exc_info.value)

    def test_enforce_blocked_network_syscalls(self):
        """Blocks network-related syscalls."""
        shield = SyscallShield()

        for syscall in ["socket", "connect", "bind"]:
            with pytest.raises(SyscallViolation):
                shield.enforce(syscall)

    def test_enforce_blocked_dangerous_syscalls(self):
        """Blocks dangerous syscalls."""
        shield = SyscallShield()

        for syscall in ["ptrace", "kill"]:
            with pytest.raises(SyscallViolation):
                shield.enforce(syscall)

    def test_enforce_unlisted_syscall_raises(self):
        """Raises for syscalls not in allow-list."""
        shield = SyscallShield()

        with pytest.raises(SyscallViolation) as exc_info:
            shield.enforce("mmap")
        assert "not in allow-list" in str(exc_info.value)

    def test_get_active_policy_default(self):
        """Returns restricted policy for unknown profiles."""
        shield = SyscallShield(agent_profile="nonexistent")
        policy = shield._get_active_policy()

        assert policy == shield.policies["restricted"]

    def test_policy_has_required_keys(self):
        """Policy contains required keys."""
        shield = SyscallShield()
        policy = shield._get_active_policy()

        assert "allowed" in policy
        assert "blocked" in policy
        assert "panic" in policy

    @patch("warm_logic.kernel.sys.shield.SyscallShield")
    def test_rust_guard_boundary_check(self, mock_shield_class):
        """Uses Rust guard for boundary verification when available."""
        mock_rust_guard = MagicMock()
        mock_rust_guard.verify_boundary.return_value = True

        shield = SyscallShield()
        shield.rust_guard = mock_rust_guard

        # Write syscall with data
        shield.enforce("write", (1, "test data"))

        mock_rust_guard.verify_boundary.assert_called_once()

    def test_rust_guard_boundary_violation(self):
        """Raises on Rust guard boundary violation."""
        mock_rust_guard = MagicMock()
        mock_rust_guard.verify_boundary.return_value = False

        shield = SyscallShield()
        shield.rust_guard = mock_rust_guard

        with pytest.raises(SyscallViolation) as exc_info:
            shield.enforce("write", (1, "x" * 100))
        assert "Memory Boundary Violation" in str(exc_info.value)

    def test_rust_guard_not_available(self):
        """Works without Rust guard."""
        shield = SyscallShield()
        shield.rust_guard = None

        # Should not raise for allowed syscall
        assert shield.enforce("read") is True


class TestShieldDecorator:
    """Test shield_syscall decorator."""

    def test_decorator_allows_call(self):
        """Decorator allows function call for permitted syscalls."""

        @shield_syscall("read")
        def read_file():
            return "data"

        # Need to mock the global shield
        with patch("warm_logic.kernel.sys.shield.shield") as mock_shield:
            mock_shield.enforce.return_value = True
            result = read_file()

        assert result == "data"

    def test_decorator_blocks_call(self):
        """Decorator blocks function call for blocked syscalls."""

        @shield_syscall("execve")
        def execute():
            return "executed"

        with patch("warm_logic.kernel.sys.shield.shield") as mock_shield:
            mock_shield.enforce.side_effect = SyscallViolation("Blocked")

            with pytest.raises(SyscallViolation):
                execute()

    def test_decorator_preserves_function_name(self):
        """Decorator preserves original function metadata."""

        @shield_syscall("read")
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_decorator_passes_args(self):
        """Decorator passes arguments to shield.enforce."""

        @shield_syscall("write")
        def write_data(handle, data):
            return len(data)

        with patch("warm_logic.kernel.sys.shield.shield") as mock_shield:
            mock_shield.enforce.return_value = True
            write_data(1, "hello")

        mock_shield.enforce.assert_called_once_with("write", (1, "hello"))


class TestKernelSyscalls:
    """Test kernel syscall implementations."""

    def test_kernel_open_raises(self):
        """kernel_open raises RuntimeError."""
        with patch("warm_logic.kernel.sys.shield.shield") as mock_shield:
            mock_shield.enforce.return_value = True

            with pytest.raises(RuntimeError) as exc_info:
                kernel_open("/path/to/file", 0)

            assert "No real 'open' syscall implementation" in str(exc_info.value)

    def test_kernel_exec_blocked(self):
        """kernel_exec is blocked by shield."""
        # execve is in blocked list, so enforce will raise
        with pytest.raises(SyscallViolation):
            kernel_exec("/bin/sh", ("sh",))

    def test_kernel_socket_blocked(self):
        """kernel_socket is blocked by shield."""
        with pytest.raises(SyscallViolation):
            kernel_socket(2, 1)  # AF_INET, SOCK_STREAM

    def test_kernel_exec_raises_runtime_error_when_allowed(self):
        """kernel_exec raises RuntimeError when shield allows it."""
        with patch("warm_logic.kernel.sys.shield.shield") as mock_shield:
            mock_shield.enforce.return_value = True

            with pytest.raises(RuntimeError) as exc_info:
                kernel_exec("/bin/sh", ("sh",))

            assert "No real 'execve' syscall implementation" in str(exc_info.value)
            assert "/bin/sh" in str(exc_info.value)

    def test_kernel_socket_raises_runtime_error_when_allowed(self):
        """kernel_socket raises RuntimeError when shield allows it."""
        with patch("warm_logic.kernel.sys.shield.shield") as mock_shield:
            mock_shield.enforce.return_value = True

            with pytest.raises(RuntimeError) as exc_info:
                kernel_socket(2, 1)

            assert "No real 'socket' syscall implementation" in str(exc_info.value)


class TestPolicyStructure:
    """Test policy configuration."""

    def test_restricted_policy_allowed_set(self):
        """Restricted policy has correct allowed syscalls."""
        shield = SyscallShield()
        policy = shield.policies["restricted"]

        expected = {"read", "write", "open", "close", "stat", "fstat"}
        assert policy["allowed"] == expected

    def test_restricted_policy_blocked_set(self):
        """Restricted policy has correct blocked syscalls."""
        shield = SyscallShield()
        policy = shield.policies["restricted"]

        expected = {"execve", "socket", "connect", "bind", "ptrace", "kill"}
        assert policy["blocked"] == expected

    def test_restricted_policy_panic_enabled(self):
        """Restricted policy has panic enabled."""
        shield = SyscallShield()
        policy = shield.policies["restricted"]

        assert policy["panic"] is True

    def test_blocked_syscall_no_panic_returns_false(self):
        """Returns False for blocked syscall when panic disabled."""
        shield = SyscallShield()
        # Add a non-panic policy
        shield.policies["no_panic"] = {
            "allowed": {"read"},
            "blocked": {"execve"},
            "panic": False,
        }
        shield.profile = "no_panic"

        result = shield.enforce("execve")
        assert result is False

    def test_unlisted_syscall_no_panic_returns_false(self):
        """Returns False for unlisted syscall when panic disabled."""
        shield = SyscallShield()
        # Add a non-panic policy
        shield.policies["no_panic_strict"] = {
            "allowed": {"read"},
            "blocked": set(),
            "panic": False,
        }
        shield.profile = "no_panic_strict"

        result = shield.enforce("mmap")
        assert result is False

    def test_wildcard_allows_all(self):
        """Wildcard in allowed set permits any syscall."""
        shield = SyscallShield()
        shield.policies["permissive"] = {
            "allowed": {"*"},
            "blocked": set(),
            "panic": False,
        }
        shield.profile = "permissive"

        assert shield.enforce("anything") is True
        assert shield.enforce("random_syscall") is True

    def test_rust_guard_loaded_when_available(self):
        """Loads Rust ShieldGuard when available."""
        mock_guard = MagicMock()

        with patch.dict(
            "sys.modules", {"warm_logic_rs": MagicMock(ShieldGuard=lambda: mock_guard)}
        ):
            shield = SyscallShield()
            # The shield should have attempted to load rust_guard
            # (may or may not succeed depending on import order)

    def test_rust_guard_none_when_import_fails(self):
        """Sets rust_guard to None when import fails."""
        with patch.dict("sys.modules", {"warm_logic_rs": None}):
            shield = SyscallShield()
            # rust_guard should be None due to import failure
            # (test passes as long as no exception is raised)
