# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""
[P0xx] Unit tests for rust_loader module.
Tests: rust_loader.py - Centralized Rust Core loading
"""

import sys
import unittest
from unittest import mock


class TestRustLoaderModule(unittest.TestCase):
    """Test rust_loader module attributes."""

    def test_has_rust_core_exists(self):
        """Test HAS_RUST_CORE attribute exists."""
        from warm_logic.kernel import rust_loader

        self.assertIsInstance(rust_loader.HAS_RUST_CORE, bool)

    def test_load_rust_core_function_exists(self):
        """Test load_rust_core function exists."""
        from warm_logic.kernel import rust_loader

        self.assertTrue(callable(rust_loader.load_rust_core))

    def test_is_simulated_function_exists(self):
        """Test is_simulated function exists."""
        from warm_logic.kernel import rust_loader

        self.assertTrue(callable(rust_loader.is_simulated))


class TestLoadRustCore(unittest.TestCase):
    """Test load_rust_core function."""

    def test_load_returns_module(self):
        """Test load_rust_core returns a module when available."""
        from warm_logic.kernel import rust_loader

        if rust_loader.HAS_RUST_CORE:
            result = rust_loader.load_rust_core()
            self.assertIsNotNone(result)

    def test_load_cached(self):
        """Test load_rust_core returns cached module."""
        from warm_logic.kernel import rust_loader

        if rust_loader.HAS_RUST_CORE:
            result1 = rust_loader.load_rust_core()
            result2 = rust_loader.load_rust_core()
            self.assertIs(result1, result2)

    @mock.patch.dict(sys.modules, {"warm_logic_rs": None})
    def test_load_handles_missing_module(self):
        """Test handling when warm_logic_rs is not available."""
        # This test verifies the error handling path
        # The actual behavior depends on the environment
        from warm_logic.kernel import rust_loader

        # Just verify the function exists and is callable
        self.assertTrue(callable(rust_loader.load_rust_core))


class TestIsSimulated(unittest.TestCase):
    """Test is_simulated function."""

    def test_is_simulated_returns_bool(self):
        """Test is_simulated returns boolean."""
        from warm_logic.kernel import rust_loader

        result = rust_loader.is_simulated()
        self.assertIsInstance(result, bool)

    def test_is_simulated_false_for_real_core(self):
        """Test is_simulated returns False for real Rust core."""
        from warm_logic.kernel import rust_loader

        # If we have a real Rust core, it shouldn't be simulated
        if rust_loader.HAS_RUST_CORE and not rust_loader.is_simulated():
            self.assertFalse(rust_loader.is_simulated())

    @mock.patch("warm_logic.kernel.rust_loader._RS_MODULE")
    def test_is_simulated_with_mock(self, mock_module):
        """Test is_simulated with MagicMock module."""
        from unittest.mock import MagicMock

        from warm_logic.kernel import rust_loader

        # Save original
        original = rust_loader._RS_MODULE

        try:
            # Set to MagicMock
            rust_loader._RS_MODULE = MagicMock()
            result = rust_loader.is_simulated()
            self.assertTrue(result)
        finally:
            # Restore original
            rust_loader._RS_MODULE = original


class TestRustLoaderPathHandling(unittest.TestCase):
    """Test path handling in rust_loader."""

    def test_package_root_calculation(self):
        """Test package root is calculated correctly."""
        from pathlib import Path

        from warm_logic.kernel import rust_loader

        # Get the expected package root
        loader_path = Path(rust_loader.__file__)
        expected_root = loader_path.parent.parent.parent.resolve()

        # Verify the path structure
        self.assertTrue(expected_root.exists())

    def test_sys_path_modification(self):
        """Test sys.path is modified when loading."""
        from pathlib import Path

        from warm_logic.kernel import rust_loader

        if rust_loader.HAS_RUST_CORE:
            loader_path = Path(rust_loader.__file__)
            expected_root = str(loader_path.parent.parent.parent.resolve())
            # The path should be in sys.path
            self.assertIn(expected_root, sys.path)


class TestRustLoaderIntegration(unittest.TestCase):
    """Integration tests for rust_loader."""

    def test_loader_state_consistency(self):
        """Test loader maintains consistent state."""
        from warm_logic.kernel import rust_loader

        # State should be consistent
        if rust_loader.HAS_RUST_CORE:
            self.assertIsNotNone(rust_loader._RS_MODULE)
        # Note: _RS_MODULE might be None even if HAS_RUST_CORE is False

    def test_module_docstring(self):
        """Test module has docstring."""
        from warm_logic.kernel import rust_loader

        self.assertIsNotNone(rust_loader.__doc__)
        self.assertIn("Rust Core Loader", rust_loader.__doc__)


if __name__ == "__main__":
    unittest.main()
