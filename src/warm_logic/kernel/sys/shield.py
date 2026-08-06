# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import functools
from typing import Any, Dict, Optional


class SyscallViolation(Exception):
    """Raised when an AI agent attempts an unauthorized system call."""

    pass


class SyscallShield:
    """
    Electronic Policy & Syscall Shield (ePASS).
    Models the behavior of an eBPF LSM (Linux Security Module) enforcer.
    """

    def __init__(self, agent_profile: str = "restricted"):
        self.profile = agent_profile
        # Production Armor: Rust ShieldGuard
        try:
            from warm_logic_rs import ShieldGuard

            self.rust_guard = ShieldGuard()
        except Exception:
            self.rust_guard = None

        # Define allowed syscalls per profile
        self.policies = {
            "restricted": {
                "allowed": {"read", "write", "open", "close", "stat", "fstat"},
                "blocked": {"execve", "socket", "connect", "bind", "ptrace", "kill"},
                "panic": True,
            },
            # hardware attestation enforcement: No root_service bypass.
            # All kernel services must define explicit restricted profiles.
        }

    def _get_active_policy(self) -> Dict[str, Any]:
        return self.policies.get(self.profile, self.policies["restricted"])

    def enforce(self, call_name: str, args: Optional[tuple[Any, ...]] = None) -> bool:
        """
        Intercepts and validates a syscall.
        In a real eBPF environment, this happens in the kernel (Ring 0).
        """
        if self.rust_guard and args:
            # Example: Verify boundary for 'write' if buffer/length provided
            if call_name == "write" and len(args) >= 2:
                # args[0] is handle, args[1] is data
                data_len = len(str(args[1]))
                # Simulate a max safe buffer of 1MB for restricted profiles
                if not self.rust_guard.verify_boundary(0, data_len, 1024 * 1024):
                    print(
                        f"🛡️  RUST SHIELD BLOCK: Memory Boundary Violation in '{call_name}'"
                    )
                    raise SyscallViolation(
                        f"Memory Boundary Violation (len={data_len})"
                    )

        policy = self._get_active_policy()

        # 1. Broad blocking
        if call_name in policy["blocked"]:
            msg = f"🛡️  ePASS SHIELD BLOCK: Syscall '{call_name}' violated profile '{self.profile}'"
            print(msg)
            if policy["panic"]:
                print("SYSTEM PANIC: SHIELD BREACHED. HALTING LOGIC CORE.")
                # We raise a specialized exception that the kernel tick loop should catch
                raise SyscallViolation(msg)
            return False

        # 2. Strict allow-listing
        if "*" not in policy["allowed"] and call_name not in policy["allowed"]:
            msg = f"🛡️  ePASS SHIELD BLOCK: Syscall '{call_name}' not in allow-list for '{self.profile}'"
            print(msg)
            if policy["panic"]:
                raise SyscallViolation(msg)
            return False

        return True


from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def shield_syscall(call_name: str) -> Callable[[F], F]:
    """Decorator for auditing syscalls."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check against global shield (using default restricted profile for userspace)
            shield.enforce(call_name, args)
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


# Global Shield Instance
shield = SyscallShield()

# --- KERNEL HOST SYSCALL BARRIERS ---
# System calls must be handled by real eBPF/LSM layers.


@shield_syscall("open")
def kernel_open(path: str, flags: int) -> int:
    raise RuntimeError(f"CRITICAL: No real 'open' syscall implementation for {path}")


@shield_syscall("execve")
def kernel_exec(path: str, args: tuple[str, ...]) -> int:
    raise RuntimeError(f"CRITICAL: No real 'execve' syscall implementation for {path}")


@shield_syscall("socket")
def kernel_socket(domain: int, socket_type: int) -> int:
    raise RuntimeError("CRITICAL: No real 'socket' syscall implementation")
