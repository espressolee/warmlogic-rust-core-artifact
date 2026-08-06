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
"""
Centralized Rust Core Loader
Unifies extension discovery and path injection across the kernel.
"""

import importlib
import logging
import sys
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("RustLoader")

# Global singleton state for loader
_RS_MODULE: Optional[Any] = None
HAS_RUST_CORE: bool = False
_rs_module_lock = threading.Lock()


def load_rust_core() -> Any:
    """
    Dynamically loads the warm_logic_rs extension (thread-safe).
    Injects the package root into sys.path to ensure local .so files are found.
    """
    global _RS_MODULE, HAS_RUST_CORE

    if _RS_MODULE is not None:
        HAS_RUST_CORE = True
        return _RS_MODULE

    with _rs_module_lock:
        # Double-checked locking
        if _RS_MODULE is not None:
            HAS_RUST_CORE = True
            return _RS_MODULE

        try:
            # Resolve package root (WarmLogic/)
            # Assuming we are in warm_logic/kernel/rust_loader.py
            pkg_root = Path(__file__).parent.parent.parent.resolve()
            if str(pkg_root) not in sys.path:
                # Insert at 0 to prioritize local dev builds over installed packages
                sys.path.insert(0, str(pkg_root))

            from unittest.mock import MagicMock

            import warm_logic_rs

            if isinstance(warm_logic_rs, MagicMock):
                print(
                    "DEBUG: RustLoader detected MagicMock in sys.modules. HAS_RUST_CORE = True (Simulated)"
                )
                _RS_MODULE = warm_logic_rs
                HAS_RUST_CORE = True
            else:
                _RS_MODULE = warm_logic_rs
                HAS_RUST_CORE = True
            return _RS_MODULE
        except ImportError as e:
            print(f"DEBUG: RustLoader ImportError: {e}")
            HAS_RUST_CORE = False
            raise SystemError(f"Critical: Failed to import warm_logic_rs: {e}")
        except Exception as e:
            # Fallback only for known broken warm_logic_rs package wrappers
            # (e.g. NameError in package __init__), not for unrelated loader errors.
            error_text = str(e)
            is_wrapper_error = (
                isinstance(e, NameError) and "warm_logic_rs" in error_text
            )
            if is_wrapper_error:
                try:
                    core_mod = importlib.import_module("warm_logic_rs.warm_logic_rs")
                    _RS_MODULE = core_mod
                    HAS_RUST_CORE = True
                    return _RS_MODULE
                except Exception:
                    HAS_RUST_CORE = False
                    raise SystemError(f"Critical: Unexpected error loading core: {e}")

            HAS_RUST_CORE = False
            raise SystemError(f"Critical: Unexpected error loading core: {e}")


def is_simulated() -> bool:
    """Returns True if the Rust Core is a MagicMock (Simulation mode)."""
    from unittest.mock import MagicMock

    return isinstance(_RS_MODULE, MagicMock)


# Initial probe to set HAS_RUST_CORE at module load time
rust_core: Optional[Any] = None
try:
    rust_core = load_rust_core()
except SystemError:
    pass
