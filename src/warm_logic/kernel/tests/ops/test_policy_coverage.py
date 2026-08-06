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
import importlib.metadata as metadata
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from warm_logic.kernel.ops.policy import (
    PluginRecord,
    _load_entry_points,
    _resolve_signature_path,
    installed_plugins,
    load_registry,
    verify_plugin,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestPolicyCoverage(WarmLogicTestCase):
    def test_record_normalization(self):
        pr = PluginRecord(
            name="test",
            editions_allowed={"  COMMUNITY ", ""},
            modules_required={" mod1 ", ""},
        )
        self.assertEqual(pr.editions_allowed, {"community"})
        self.assertEqual(pr.modules_required, {"mod1"})

    def test_verify_plugin_registry_miss(self):
        flags = SimpleNamespace()
        errs = verify_plugin("missing", flags, {})
        self.assertIn("not present", errs[0])

    @mock.patch("warm_logic.kernel.ops.policy._RUST_POLICY", None)
    def test_verify_checks(self):
        # Setup Record
        rec = PluginRecord(
            name="p1",
            editions_allowed={"enterprise"},
            modules_required={"mod_a"},
            package="pkg_p1",
            min_version="1.0.0",
            entry_point="ep.p1",
            signature="sig",
            signature_path=Path("sig.txt"),
        )
        registry = {"p1": rec}

        # 1. Edition Fail
        flags = SimpleNamespace(edition="community", modules={"mod_a"})
        errs = verify_plugin("p1", flags, registry)
        self.assertTrue(any("edition" in e for e in errs))

        # 2. Modules Fail
        flags = SimpleNamespace(edition="enterprise", modules=set())
        errs = verify_plugin("p1", flags, registry)
        self.assertTrue(any("missing required modules" in e for e in errs))

        # 3. Package Check
        fake_eps = {"ep.p1": "obj"}

        with mock.patch("warm_logic.kernel.ops.policy.metadata.version") as mock_ver:
            with mock.patch(
                "warm_logic.kernel.ops.policy._load_entry_points", return_value=fake_eps
            ):
                with mock.patch.object(Path, "exists", return_value=True):
                    with mock.patch.object(
                        Path, "read_text", return_value="sig"
                    ):  # Valid Sig
                        # Success case
                        mock_ver.return_value = "1.0.0"
                        flags = SimpleNamespace(edition="enterprise", modules={"mod_a"})
                        errs = verify_plugin("p1", flags, registry)
                        self.assertEqual(errs, [])

                        # Version Low
                        mock_ver.return_value = "0.9.9"
                        errs = verify_plugin("p1", flags, registry)
                        self.assertTrue(any("version" in e for e in errs))

                        # Package Missing
                        mock_ver.side_effect = metadata.PackageNotFoundError
                        errs = verify_plugin("p1", flags, registry)
                        self.assertTrue(any("not installed" in e for e in errs))

        # 4. Entry Point Missing
        with mock.patch(
            "warm_logic.kernel.ops.policy.metadata.version", return_value="1.0"
        ):
            with mock.patch(
                "warm_logic.kernel.ops.policy._load_entry_points", return_value={}
            ):
                flags = SimpleNamespace(edition="enterprise", modules={"mod_a"})
                errs = verify_plugin("p1", flags, registry)
                self.assertTrue(any("entry point" in e for e in errs))

        # 5. Signature Fail
        with mock.patch(
            "warm_logic.kernel.ops.policy.metadata.version", return_value="1.0"
        ):
            with mock.patch(
                "warm_logic.kernel.ops.policy._load_entry_points",
                return_value={"ep.p1": 1},
            ):
                flags = SimpleNamespace(edition="enterprise", modules={"mod_a"})

                # Missing file
                with mock.patch.object(Path, "exists", return_value=False):
                    errs = verify_plugin("p1", flags, registry)
                    self.assertTrue(any("signature file missing" in e for e in errs))

                # Mismatch
                with mock.patch.object(Path, "exists", return_value=True):
                    with mock.patch.object(Path, "read_text", return_value="bad_sig"):
                        errs = verify_plugin("p1", flags, registry)
                        self.assertTrue(any("signature mismatch" in e for e in errs))

    def test_load_registry(self):
        # Missing file
        with self.assertRaises(FileNotFoundError):
            load_registry(Path("bad"))

        # Valid JSON
        json_data = """
        {
            "plugins": [
                {
                    "name": "p1",
                    "package": "pkg1",
                    "signature_path": "sig.txt"
                },
                {"name": "p2"},
                {"bad": "entry"}
            ]
        }
        """  # p2 minimal, bad entry skipped

        with mock.patch.object(Path, "exists", return_value=True):
            with mock.patch.object(Path, "read_text", return_value=json_data):
                reg = load_registry(Path("reg.json"))
                self.assertIn("p1", reg)
                self.assertIn("p2", reg)
                self.assertEqual(len(reg), 2)

                # Check path resolution logic embedded
                # sig.txt relative to reg.json -> parent/sig.txt
                self.assertEqual(
                    reg["p1"].signature_path, Path("sig.txt")
                )  # It stores as path object

    def test_load_registry_fail(self):
        # Case: Malformed JSON or other exception during load
        with mock.patch.object(Path, "exists", return_value=True):
            with mock.patch.object(
                Path, "read_text", side_effect=Exception("Read Error")
            ):
                with self.assertRaises(RuntimeError):
                    load_registry(Path("p"))

    def test_installed_plugins(self):
        registry = {"p1": PluginRecord(name="p1", entry_point="ep1", package="pkg1")}

        eps = {"ep1": 1}
        with mock.patch(
            "warm_logic.kernel.ops.policy._load_entry_points", return_value=eps
        ):
            # Case 1: Package Installed
            with mock.patch(
                "warm_logic.kernel.ops.policy.metadata.version", return_value="1.0"
            ):
                res = installed_plugins(registry)
                self.assertEqual(res, ["p1"])

            # Case 2: Package Missing
            with mock.patch(
                "warm_logic.kernel.ops.policy.metadata.version",
                side_effect=metadata.PackageNotFoundError,
            ):
                res = installed_plugins(registry)
                self.assertEqual(res, [])

    def test_load_entry_points_compat(self):
        # Test the fallback logic in _load_entry_points

        # 1. Standard (Python 3.10+)
        ep = mock.Mock()
        ep.name = "ep1"
        with mock.patch(
            "warm_logic.kernel.ops.policy.metadata.entry_points", return_value=[ep]
        ):
            res = _load_entry_points()
            self.assertIn("ep1", res)

    def test_load_entry_points_compat_select(self):
        ep = mock.Mock()
        ep.name = "ep1"

        mock_eps = mock.Mock()
        mock_eps.select.return_value = [ep]

        def side_effect(*args, **kwargs):
            if kwargs:
                raise TypeError
            return mock_eps

        with mock.patch(
            "warm_logic.kernel.ops.policy.metadata.entry_points",
            side_effect=side_effect,
        ):
            res = _load_entry_points()
            self.assertIn("ep1", res)

    def test_load_entry_points_compat_dict(self):
        ep = mock.Mock()
        ep.name = "ep1"

        # Fallback to dict if .select not present
        mock_eps = {"warm_logic.plugins": [ep]}

        def side_effect(*args, **kwargs):
            if kwargs:
                raise TypeError
            return mock_eps  # It is a dict, so no .select attribute

        with mock.patch(
            "warm_logic.kernel.ops.policy.metadata.entry_points",
            side_effect=side_effect,
        ):
            res = _load_entry_points()
            self.assertIn("ep1", res)

    def test_load_entry_points_compat_empty(self):
        # Fallback to empty if neither
        def side_effect(*args, **kwargs):
            if kwargs:
                raise TypeError
            return []  # List has no .select and is not dict

        with mock.patch(
            "warm_logic.kernel.ops.policy.metadata.entry_points",
            side_effect=side_effect,
        ):
            res = _load_entry_points()
            self.assertEqual(res, {})

    def test_resolve_path_absolute(self):
        p = _resolve_signature_path(Path("reg.json"), "/abs/sig.txt")
        self.assertEqual(p, Path("/abs/sig.txt"))
