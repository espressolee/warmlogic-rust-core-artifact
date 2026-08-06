# Top-level conftest: shared hooks and module cleanup to avoid import collisions.
import sys

import pytest

from warm_logic.kernel import rust_loader

# Avoid module name collisions with nested warm_logic_core/cli/tests modules.
for name in [
    "tests.test_backup_restore",
    "tests.test_compat_check",
    "tests.test_compliance_bundle",
    "tests.test_devenv_commands",
    "tests.test_license_command",
    "tests.test_plugin_cli_integration",
    "tests.test_plugin_commands",
]:
    sys.modules.pop(name, None)


try:
    _RUST_BASELINE_MODULE = rust_loader.load_rust_core()
    _RUST_BASELINE_HAS = True
except Exception:
    _RUST_BASELINE_MODULE = rust_loader._RS_MODULE
    _RUST_BASELINE_HAS = rust_loader.HAS_RUST_CORE


@pytest.fixture(autouse=True)
def _restore_rust_loader_state():
    """
    Keep Rust loader globals deterministic across tests.
    Several test suites patch HAS_RUST_CORE directly and can leak state
    between workers/files unless we restore a known baseline.
    """
    yield
    rust_loader._RS_MODULE = _RUST_BASELINE_MODULE
    rust_loader.HAS_RUST_CORE = _RUST_BASELINE_HAS
