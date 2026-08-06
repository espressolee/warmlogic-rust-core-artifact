import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from warm_logic.kernel.sys.api import FFIBridge


def verify_substrate():
    print("Initializing Sovereign Substrate Interface...")

    # Test 1: Check Compliance
    if FFIBridge.check_no_std_compliance():
        print("Unikernel (no_std) Compliance Check Passed.")
    else:
        print("Unikernel Compliance Failed.")
        sys.exit(1)

    # Test 2: Call Rust Kernel
    print("  Invoking Simulated Rust Kernel...")
    response = FFIBridge.call_rust_kernel("bootstrap", b"payload")

    if response == b"ACK_FROM_RUST":
        print("FFI Bridge Active (Simulated).")
    else:
        print(f"FFI Bridge Malfunction: {response}")
        sys.exit(1)


if __name__ == "__main__":
    verify_substrate()
