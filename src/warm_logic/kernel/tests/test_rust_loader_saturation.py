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
import importlib
import sys
import unittest
from unittest import mock

from warm_logic.kernel import rust_loader


class TestRustLoaderSaturation(unittest.TestCase):
    def setUp(self):
        # Reset global state for individual tests
        rust_loader._RS_MODULE = None
        rust_loader.HAS_RUST_CORE = False

    def test_load_rust_core_singleton(self):
        """Line 26-27: return if already loaded."""
        rust_loader._RS_MODULE = "ALREADY_LOADED"
        res = rust_loader.load_rust_core()
        self.assertEqual(res, "ALREADY_LOADED")

    def test_load_rust_core_mock_detection(self):
        """Line 40-47: Success via MagicMock."""
        mock_rs = mock.MagicMock()
        with mock.patch.dict("sys.modules", {"warm_logic_rs": mock_rs}):
            res = rust_loader.load_rust_core()
            self.assertTrue(rust_loader.HAS_RUST_CORE)
            self.assertEqual(res, mock_rs)
            self.assertTrue(rust_loader.is_simulated())

    def test_load_rust_core_success_real(self):
        """Line 48-50: Success via real module."""

        class RealModule:
            pass

        real_mod = RealModule()
        with mock.patch.dict("sys.modules", {"warm_logic_rs": real_mod}):
            res = rust_loader.load_rust_core()
            self.assertTrue(rust_loader.HAS_RUST_CORE)
            self.assertFalse(rust_loader.is_simulated())

    def test_load_rust_core_import_error(self):
        """Line 51-54: Raise SystemError on ImportError."""
        real_import = __import__

        def surgical_import(name, *args, **kwargs):
            if name == "warm_logic_rs":
                raise ImportError("no")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=surgical_import):
            with mock.patch("importlib.import_module", side_effect=ImportError("no")):
                with self.assertRaises(SystemError):
                    rust_loader.load_rust_core()

    def test_load_rust_core_wrapper_fallback(self):
        """Line 61-71: Fallback for NameError in wrapper."""
        real_import = __import__

        def surgical_import(name, *args, **kwargs):
            if name == "warm_logic_rs":
                raise NameError("name 'warm_logic_rs' is not defined")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=surgical_import):
            mock_core = mock.MagicMock()
            with mock.patch(
                "importlib.import_module", return_value=mock_core
            ) as mock_mod:
                res = rust_loader.load_rust_core()
                self.assertEqual(res, mock_core)
                self.assertTrue(rust_loader.HAS_RUST_CORE)
                mock_mod.assert_called_with("warm_logic_rs.warm_logic_rs")

    def test_load_rust_core_wrapper_fallback_fail(self):
        """Line 70-71: SystemError if fallback also fails."""
        real_import = __import__

        def surgical_import(name, *args, **kwargs):
            if name == "warm_logic_rs":
                raise NameError("name 'warm_logic_rs' is not defined")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=surgical_import):
            with mock.patch(
                "importlib.import_module", side_effect=Exception("fallback fail")
            ):
                with self.assertRaises(SystemError):
                    rust_loader.load_rust_core()

    def test_load_rust_core_unexpected_exception(self):
        """Line 73-74: SystemError on non-wrapper Exception."""
        real_import = __import__

        def surgical_import(name, *args, **kwargs):
            if name == "warm_logic_rs":
                raise RuntimeError("something else")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=surgical_import):
            with self.assertRaises(SystemError):
                rust_loader.load_rust_core()

    def test_path_injection(self):
        """Line 32-35: sys.path injection."""
        rust_loader._RS_MODULE = None
        with mock.patch.object(sys, "path", sys.path.copy()):
            with mock.patch.dict("sys.modules", {"warm_logic_rs": mock.MagicMock()}):
                with mock.patch("warm_logic.kernel.rust_loader.Path") as mock_path:
                    mock_path.return_value.parent.parent.parent.resolve.return_value = (
                        "/not/in/path"
                    )
                    rust_loader.load_rust_core()
                    self.assertIn("/not/in/path", sys.path)

    def test_module_probe_exception(self):
        """Line 85-86: module level SystemError catch."""
        # Instead of patching the function (which gets overwritten on reload),
        # we patch the underlying __import__ to raise the error that load_rust_core will then turn into SystemError.
        real_import = __import__

        def fail_import(name, *args, **kwargs):
            if name == "warm_logic_rs":
                raise ImportError("force fail")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fail_import):
            # Also mock importlib.import_module for the fallback path
            with mock.patch(
                "importlib.import_module", side_effect=ImportError("force fail")
            ):
                importlib.reload(rust_loader)
                self.assertFalse(rust_loader.HAS_RUST_CORE)


if __name__ == "__main__":
    unittest.main()
