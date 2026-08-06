import asyncio
import os
import sys

import pytest

# Ensure src is in path so we can import warm_logic
src_path = os.path.abspath("src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Ensure rust_core is in path for editable installs
rust_core_path = os.path.abspath("rust_core")
if rust_core_path not in sys.path:
    sys.path.insert(0, rust_core_path)

# Try real Rust module first, fall back to mock only if unavailable
_USE_RUST_MOCK = os.environ.get("WARMLOGIC_USE_MOCK", "0") == "1"
_WARM_LOGIC_RS_REF = None

if not _USE_RUST_MOCK:
    try:
        import warm_logic_rs

        # Verify critical classes are available
        assert hasattr(warm_logic_rs, "Vote"), "Vote not exported"
        assert hasattr(warm_logic_rs, "BFTEngine"), "BFTEngine not exported"
        _WARM_LOGIC_RS_REF = warm_logic_rs
        print("DEBUG: Using real warm_logic_rs Rust module")
    except Exception as e:
        print(f"DEBUG: Rust module unavailable ({e}), falling back to mock")
        _USE_RUST_MOCK = True

if _USE_RUST_MOCK:
    # Ensure root is in path for warm_logic_rs_mock
    root_path = os.path.abspath(".")
    if root_path not in sys.path:
        sys.path.insert(0, root_path)

    # Use the complete mock from scripts/debug
    scripts_debug_path = os.path.abspath("scripts/debug")
    if scripts_debug_path not in sys.path:
        sys.path.insert(0, scripts_debug_path)

    try:
        import warm_logic_rs_mock

        _WARM_LOGIC_RS_REF = warm_logic_rs_mock
        sys.modules["warm_logic_rs"] = warm_logic_rs_mock
        print("DEBUG: Using warm_logic_rs_mock fallback")
    except ImportError:
        print("DEBUG: Global conftest failed to import warm_logic_rs_mock")

from warm_logic.kernel import rust_loader

try:
    _RUST_BASELINE_MODULE = rust_loader.load_rust_core()
    _RUST_BASELINE_HAS = True
except Exception:
    _RUST_BASELINE_MODULE = rust_loader._RS_MODULE
    _RUST_BASELINE_HAS = rust_loader.HAS_RUST_CORE


def _restore_warm_logic_rs_module():
    """Prevent cross-test pollution of the warm_logic_rs import state."""
    if _WARM_LOGIC_RS_REF is None:
        return

    from unittest.mock import MagicMock

    submodule = sys.modules.get("warm_logic_rs.warm_logic_rs")
    if isinstance(submodule, MagicMock):
        sys.modules.pop("warm_logic_rs.warm_logic_rs", None)

    current = sys.modules.get("warm_logic_rs")
    if isinstance(current, MagicMock):
        sys.modules.pop("warm_logic_rs", None)
        current = None

    if current is None:
        sys.modules["warm_logic_rs"] = _WARM_LOGIC_RS_REF
        return

    if (
        not hasattr(current, "RustZKProofGenerator")
        and not hasattr(current, "SovereignStore")
        and current is not _WARM_LOGIC_RS_REF
    ):
        sys.modules["warm_logic_rs"] = _WARM_LOGIC_RS_REF


def _reset_state_attestor_singleton():
    """Reset StateAttestor singleton to prevent cross-test pollution."""
    try:
        from warm_logic.kernel.sys.cryptography import StateAttestor

        StateAttestor._instance = None
        StateAttestor._keypair = None
        StateAttestor._sealed_private_key = None
    except ImportError:
        pass  # Module not yet imported


def pytest_runtest_setup(item):
    _restore_warm_logic_rs_module()
    _reset_state_attestor_singleton()


def pytest_sessionstart(session):
    """Patch rust_loader if mock is being used."""
    _restore_warm_logic_rs_module()
    if _USE_RUST_MOCK and "warm_logic.kernel.rust_loader" in sys.modules:
        import warm_logic_rs_mock

        rl = sys.modules["warm_logic.kernel.rust_loader"]
        rl._RS_MODULE = warm_logic_rs_mock
        rl.HAS_RUST_CORE = True
        rl.rust_core = warm_logic_rs_mock


@pytest.fixture(scope="session", autouse=True)
def _close_lingering_default_event_loop():
    """
    Python 3.13 + pytest-asyncio can leave a default loop allocated on worker exit.
    Close it explicitly to avoid unclosed event-loop/socket ResourceWarnings.
    """
    yield
    policy = asyncio.get_event_loop_policy()
    local_state = getattr(policy, "_local", None)
    loop = getattr(local_state, "_loop", None)
    if loop is not None and not loop.is_closed():
        loop.close()
    try:
        asyncio.set_event_loop(None)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _restore_rust_loader_state():
    """
    Keep rust_loader globals deterministic across all test roots
    (both tests/ and src/warm_logic/kernel/tests/).
    """
    yield
    rust_loader._RS_MODULE = _RUST_BASELINE_MODULE
    rust_loader.HAS_RUST_CORE = _RUST_BASELINE_HAS


@pytest.fixture(autouse=True)
def _close_stray_event_loop_per_test():
    """
    Close non-running default loops left behind between tests.
    This prevents pytest unraisable ResourceWarnings on Python 3.13.
    """
    yield
    policy = asyncio.get_event_loop_policy()
    local_state = getattr(policy, "_local", None)
    loop = getattr(local_state, "_loop", None)
    if loop is not None and not loop.is_closed() and not loop.is_running():
        loop.close()
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass
