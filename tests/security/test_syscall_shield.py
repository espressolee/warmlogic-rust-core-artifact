import pytest

from warm_logic.kernel.sys.shield import (
    SyscallViolation,
    kernel_exec,
    kernel_open,
    kernel_socket,
    shield,
)


def test_syscall_shielding():
    print("\nTesting ePASS Shield...")

    # 1. Allowed Call (open) should check shield but fail due to missing implementation (RuntimeError), NOT SyscallViolation
    # Note: 'open' is in ALLOWED policies["restricted"]["allowed"] = {"read", "write", "open", ...}
    try:
        # It's an allowed syscall, so it passes the shield but fails the implementation
        with pytest.raises(RuntimeError) as exc:
            kernel_open("/tmp/data.txt", 0)
        assert "No real 'open'" in str(exc.value)
        print("✅ Allowed Call Passed Shield (but failed implementation as expected).")
    except SyscallViolation:
        pytest.fail("Allowed call was blocked by shield!")

    # 2. Blocked Call (EXECVE)
    # 'execve' is in policies["restricted"]["blocked"]
    print("Testing Blocked Call (execve)...")
    with pytest.raises(SyscallViolation) as excinfo:
        kernel_exec("/usr/bin/sh", ("-c", "rm -rf /"))

    print(f"🛑 Blocked Call Successfully Triggered Panic: {excinfo.value}")
    assert "execve" in str(excinfo.value)

    # 3. Blocked Call (SOCKET)
    # 'socket' is in policies["restricted"]["blocked"]
    print("Testing Blocked Call (socket)...")
    with pytest.raises(SyscallViolation):
        kernel_socket(2, 1)  # AF_INET, SOCK_STREAM

    print("✅ All Shielding Tests Passed.")


if __name__ == "__main__":
    test_syscall_shielding()
