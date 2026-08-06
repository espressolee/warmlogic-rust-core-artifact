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
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from warm_logic.kernel.ops.policy import (
    PluginRecord,
    installed_plugins,
    load_registry,
    verify_plugin,
)


class TestPolicy(unittest.TestCase):
    def test_record_normalization(self):
        """Verify PluginRecord normalizes sets (lowercase, strip)."""
        record = PluginRecord(
            name="TestPlugin",
            editions_allowed={" Community ", "ENTERPRISE"},
            modules_required={" CORE ", "network"},
        )
        self.assertEqual(record.editions_allowed, {"community", "enterprise"})
        self.assertEqual(record.modules_required, {"core", "network"})

    def test_verify_plugin_errors(self):
        """Verify various error conditions in verify_plugin."""
        registry = {
            "valid_plugin": PluginRecord(name="valid_plugin"),
            "edition_plugin": PluginRecord(
                name="edition_plugin", editions_allowed={"enterprise"}
            ),
            "modules_plugin": PluginRecord(
                name="modules_plugin", modules_required={"heavy_compute"}
            ),
            "package_plugin": PluginRecord(name="package_plugin", package="some-pkg"),
            "version_plugin": PluginRecord(
                name="version_plugin", package="ver-pkg", min_version="2.0.0"
            ),
            "entry_plugin": PluginRecord(name="entry_plugin", entry_point="my.entry"),
            "sig_plugin": PluginRecord(
                name="sig_plugin",
                signature="valid_sig",
                signature_path=Path("/tmp/sig"),
            ),
        }

        # flags mock
        flags = MagicMock()
        flags.edition = "community"
        flags.modules = {"core"}

        # 1. Missing in registry
        errors = verify_plugin("unknown", flags, registry)
        self.assertIn("plugin unknown not present in registry", errors)

        # 2. Edition mismatch
        errors = verify_plugin("edition_plugin", flags, registry)
        self.assertIn("edition community not allowed for plugin edition_plugin", errors)

        # 3. Missing modules
        errors = verify_plugin("modules_plugin", flags, registry)
        self.assertIn("missing required modules for modules_plugin", errors[0])

        # 4. Package checks (Mocking metadata)
        with patch("importlib.metadata.version") as mock_ver:
            # Case 4a: Package not installed
            mock_ver.side_effect = ImportError("No module named...")
            # Ideally verify_plugin expects PackageNotFoundError from importlib.metadata
            # checking implementation: except metadata.PackageNotFoundError
            # We need to import PackageNotFoundError to mock it properly or raise the correct one
            from importlib.metadata import PackageNotFoundError

            mock_ver.side_effect = PackageNotFoundError

            errors = verify_plugin("package_plugin", flags, registry)
            self.assertIn("package some-pkg not installed", errors)

            # Case 4b: Version mismatch
            mock_ver.side_effect = None
            mock_ver.return_value = "1.0.0"
            errors = verify_plugin("version_plugin", flags, registry)
            self.assertIn("package ver-pkg version 1.0.0 < required 2.0.0", errors)

            # Case 4b-2: Version success (ver >= min)
            mock_ver.return_value = "2.0.0"
            errors = verify_plugin("version_plugin", flags, registry)
            self.assertEqual(errors, [])

    @patch("warm_logic.kernel.ops.policy._RUST_POLICY", None)
    @patch("warm_logic.kernel.ops.policy._load_entry_points")
    def test_verify_plugin_entry_and_sig(self, mock_load_eps):
        """Verify entry point and signature checks."""
        # Setup registry
        sig_path = MagicMock()
        sig_path.exists.return_value = True
        sig_path.read_text.return_value = "valid_sig"

        registry = {
            "entry_plugin": PluginRecord(name="entry_plugin", entry_point="my.entry"),
            "sig_plugin": PluginRecord(
                name="sig_plugin", signature="valid_sig", signature_path=sig_path
            ),
            "bad_sig_plugin": PluginRecord(
                name="bad_sig_plugin", signature="valid_sig", signature_path=sig_path
            ),
        }

        flags = MagicMock()
        flags.edition = "community"
        flags.modules = set()

        # 1. Entry point missing
        mock_load_eps.return_value = {}
        errors = verify_plugin("entry_plugin", flags, registry)
        self.assertIn("entry point my.entry not registered", errors)

        # 2. Signature Checks
        # Valid signature
        errors = verify_plugin("sig_plugin", flags, registry)
        self.assertEqual(errors, [])

        # Missing signature file
        sig_path.exists.return_value = False
        errors = verify_plugin("sig_plugin", flags, registry)
        self.assertIn("signature file missing", errors[0])

        # Mismatch signature
        sig_path.exists.return_value = True
        sig_path.read_text.return_value = "WRONG_SIG"
        errors = verify_plugin("bad_sig_plugin", flags, registry)
        self.assertIn("signature mismatch", errors[0])

        # Case: Signature check with NO signature string but path exists (missed branch)
        # We need a record with signature_path but signature=None
        # The code is: elif record.signature: ...
        # If signature is None, it skips inequality check.
        # But we also have: if not record.signature_path.exists()

        record_nosig = PluginRecord(
            name="nosig", signature_path=sig_path, signature=None
        )
        registry["nosig"] = record_nosig

        # Ensure path exists so we hit the elif record.signature check
        sig_path.exists.return_value = True
        errors = verify_plugin("nosig", flags, registry)
        self.assertEqual(errors, [])

    def test_load_registry(self):
        """Test loading registry from JSON."""
        # 1. Missing file
        with self.assertRaises(FileNotFoundError):
            load_registry(Path("/non/existent"))

        # 2. Valid file with relative signature path
        json_data = json.dumps(
            {
                "plugins": [
                    {"name": "p1", "package": "pkg1", "signature_path": "sigs/p1.sig"},
                    {"name": "p2_nosig", "package": "pkg2"},  # Missing sig path
                    {"no_name": "skipped"},
                ]
            }
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=json_data),
        ):
            reg_path = Path("/etc/registry.json")
            registry = load_registry(reg_path)

            self.assertIn("p1", registry)
            self.assertEqual(registry["p1"].package, "pkg1")
            # Check relative path resolution
            expected_sig = reg_path.parent / "sigs/p1.sig"
            self.assertEqual(registry["p1"].signature_path, expected_sig)

            # Check p2_nosig (no signature_path)
            self.assertIn("p2_nosig", registry)
            self.assertIsNone(registry["p2_nosig"].signature_path)

        # 3. Malformed JSON
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="{bad_json"),
        ):
            with self.assertRaises(RuntimeError):
                load_registry(Path("x"))

    @patch("warm_logic.kernel.ops.policy._load_entry_points")
    @patch("importlib.metadata.version")
    def test_installed_plugins(self, mock_ver, mock_eps):
        """Test installed_plugins filtering."""
        registry = {
            "p1": PluginRecord(name="p1", entry_point="ep1", package="pkg1"),
            "p2": PluginRecord(name="p2", entry_point="ep2"),  # No package, just EP
            "p3": PluginRecord(
                name="p3", entry_point="ep3", package="pkg3"
            ),  # Missing pkg
            "p4": PluginRecord(name="p4", entry_point="ep4"),  # Missing EP
        }

        # Mocks
        # EPs only has ep1, ep2, ep3
        mock_eps.return_value = {
            "ep1": MagicMock(),
            "ep2": MagicMock(),
            "ep3": MagicMock(),
        }

        # Package versions
        def version_side_effect(name):
            if name == "pkg1":
                return "1.0"
            from importlib.metadata import PackageNotFoundError

            raise PackageNotFoundError

        mock_ver.side_effect = version_side_effect

        result = installed_plugins(registry)

        self.assertIn("p1", result)  # OK
        self.assertIn("p2", result)  # OK (No package req)
        self.assertNotIn("p3", result)  # Missing Package
        self.assertNotIn("p4", result)  # Missing EP

    def test_resolve_signature_path(self):
        from warm_logic.kernel.ops.policy import _resolve_signature_path

        base = Path("/opt/reg.json")

        # Absolute
        self.assertEqual(_resolve_signature_path(base, "/tmp/sig"), Path("/tmp/sig"))
        # Relative
        self.assertEqual(_resolve_signature_path(base, "sig"), Path("/opt/sig"))

    def test_load_entry_points_polyfill(self):
        """Test _load_entry_points fallback logic indirectly if possible or verify main path."""
        # Since logic switches on Python version/AttributeError, we can mock importlib.metadata.entry_points
        # to raise TypeError to test fallback.
        from warm_logic.kernel.ops.policy import _load_entry_points

        # 1. Modern (group arg supported)
        with patch("importlib.metadata.entry_points") as mock_ep:
            m_ep = MagicMock()
            m_ep.name = "plugin1"
            mock_ep.return_value = [m_ep]  # It returns iterable or SelectableGroups

            # If it returns a list directly (Py3.10+ behavior when group is passed)
            res = _load_entry_points()
            self.assertIn("plugin1", res)

        # 2. Old (TypeError on group arg)
        with patch("importlib.metadata.entry_points") as mock_ep:
            mock_ep.side_effect = TypeError

            # Fallback 1: .select()
            mock_eps_obj = MagicMock()
            m_ep = MagicMock()
            m_ep.name = "plugin2"
            mock_eps_obj.select.return_value = [m_ep]

            # Reset side effect for specific call pattern?
            # Actually entry_points() (no args) called inside except block.
            # We need checking args inside side_effect

            def side_effect(*args, **kwargs):
                if kwargs.get("group"):
                    raise TypeError
                return mock_eps_obj

            mock_ep.side_effect = side_effect

            res = _load_entry_points()
            self.assertIn("plugin2", res)

            # Fallback 2: dict-like
            del mock_eps_obj.select  # Remove select method

            mock_eps_obj.get.return_value = [m_ep]
            # Isinstance check failure mock is hard because MagicMock is dict-like?
            # We just verify it hits one of the branches.

            # Ideally simply covering modern path (Py3.13) is sufficient for Saturation.
            # But let's stick to logic coverage.

    def test_load_entry_points_legacy(self):
        """Test _load_entry_points fallback logic (dictionary return)."""
        from warm_logic.kernel.ops.policy import _load_entry_points

        # Case: TypeError -> fallback -> dict result
        with patch("importlib.metadata.entry_points") as mock_ep:
            # We need standard call to raise TypeError
            # But the fallback call (no args) to return a DICT

            m_ep = MagicMock()
            m_ep.name = "plugin_dict"

            def side_effect(*args, **kwargs):
                if kwargs.get("group") == "warm_logic.plugins":
                    raise TypeError("New API not supported")
                # Fallback call usually has no args or different args
                return {"warm_logic.plugins": [m_ep]}

            mock_ep.side_effect = side_effect

            res = _load_entry_points()
            self.assertIn("plugin_dict", res)

    def test_load_entry_points_empty_fallback(self):
        """Test _load_entry_points fallback to empty dict."""
        from warm_logic.kernel.ops.policy import _load_entry_points

        with patch("importlib.metadata.entry_points") as mock_ep:
            # Return something that is neither dict nor has select
            mock_ep.side_effect = TypeError

            # When called with no args inside the except block
            def side_effect(*args, **kwargs):
                if kwargs.get("group"):
                    raise TypeError
                return "Not a dict"

            mock_ep.side_effect = side_effect

            res = _load_entry_points()
            self.assertEqual(res, {})


if __name__ == "__main__":
    unittest.main()
