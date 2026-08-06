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
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import warm_logic.kernel.rust_loader as rust_loader


class WarmLogicTestCase(unittest.IsolatedAsyncioTestCase):
    """
    Base class for all WarmLogic Kernel tests.
    Enforces strict isolation of:
    1. Filesystem (tempdir per test)
    2. rust_loader state (HAS_RUST_CORE patched to False by default)
    3. Global Singletons
    """

    # Set to True in subclass if you specifically need to test Rust integration
    USE_RUST_CORE = False

    def setUp(self):
        super().setUp()

        # 1. Create Isolated Directory
        self.test_dir = tempfile.mkdtemp(prefix="wl_test_")
        self.addCleanup(self._cleanup_dir)

        # 2. Patch Rust Loader
        # We patch it at the module level to ensure all imports see the same value
        self.rust_patcher = patch(
            "warm_logic.kernel.rust_loader.HAS_RUST_CORE", self.USE_RUST_CORE
        )
        self.rust_patcher.start()

        # 3. Reset Singleton State (Just in case)
        # Force reload or reset if needed. For now, patching HAS_RUST_CORE is usually enough
        # as long as code checks the flag.
        # But specifically reset the module global if it was dirty
        self._original_rs_module = rust_loader._RS_MODULE
        if not self.USE_RUST_CORE:
            rust_loader._RS_MODULE = None
            self._purge_mocked_rust_modules()

        # 4. Reset Speculative Buffer
        from warm_logic.kernel.ops.speculative_buffer import speculative_buffer

        speculative_buffer._buffers = {}
        speculative_buffer._active_overlay = None

        # 5. Reset Kernel Singletons
        from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey
        from warm_logic.kernel.substrate.stitch_server import StitchServer

        ChaosMonkey.reset()
        StitchServer.reset()

    def tearDown(self):
        super().tearDown()
        self.rust_patcher.stop()
        # Restore original module state
        if not self.USE_RUST_CORE:
            rust_loader._RS_MODULE = self._original_rs_module

    def _cleanup_dir(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _purge_mocked_rust_modules(self):
        """
        Remove leaked mocked rust modules left in sys.modules by prior tests.
        This prevents cross-test contamination when load_rust_core() re-imports.
        """
        for mod_name, mod in list(sys.modules.items()):
            if (mod_name == "warm_logic_rs" or mod_name.startswith("warm_logic_rs.")) and isinstance(mod, MagicMock):
                sys.modules.pop(mod_name, None)

    def get_temp_path(self, filename: str) -> str:
        """Helper to get a path inside the isolated test dir."""
        return os.path.join(self.test_dir, filename)
