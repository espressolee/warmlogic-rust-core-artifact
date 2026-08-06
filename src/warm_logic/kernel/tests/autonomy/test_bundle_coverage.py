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
Comprehensive tests for autonomy/bundle.py - LogosBundler
Target: 80%+ coverage
"""

import io
import os
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.autonomy.bundle import LogosBundler


class TestLogosBundlerInit(unittest.TestCase):
    """Test LogosBundler initialization."""

    def test_init_default_path(self):
        """Test initialization with default path."""
        bundler = LogosBundler()
        self.assertEqual(bundler.root_path, os.path.abspath("."))
        self.assertIn(".git", bundler.ignore_dirs)
        self.assertIn("__pycache__", bundler.ignore_dirs)

    def test_init_custom_path(self):
        """Test initialization with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundler = LogosBundler(root_path=tmpdir)
            self.assertEqual(bundler.root_path, tmpdir)


class TestCreateBundle(unittest.TestCase):
    """Test bundle creation."""

    def test_create_bundle_simple(self):
        """Test creating a bundle from a simple directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("# test python file\n")

            bundler = LogosBundler(root_path=tmpdir)
            bundle_bytes, manifest_hash = bundler.create_bundle()

            # Verify bundle is created
            self.assertIsInstance(bundle_bytes, bytes)
            self.assertGreater(len(bundle_bytes), 0)
            self.assertEqual(len(manifest_hash), 64)  # SHA256 hex

    def test_create_bundle_multiple_files(self):
        """Test bundle with multiple file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create various file types
            for ext in [".py", ".pyi", ".rs", ".toml", ".md"]:
                with open(os.path.join(tmpdir, f"test{ext}"), "w") as f:
                    f.write(f"# content for {ext}\n")

            # Create file that should be ignored
            with open(os.path.join(tmpdir, "test.txt"), "w") as f:
                f.write("ignored\n")

            bundler = LogosBundler(root_path=tmpdir)
            bundle_bytes, _ = bundler.create_bundle()

            # Verify contents
            buf = io.BytesIO(bundle_bytes)
            with tarfile.open(fileobj=buf, mode="r:gz") as tar:
                names = tar.getnames()
                self.assertEqual(len(names), 5)  # Only 5 valid extensions
                self.assertNotIn("test.txt", names)

    def test_create_bundle_ignores_dirs(self):
        """Test that ignored directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create ignored directory
            git_dir = os.path.join(tmpdir, ".git")
            os.makedirs(git_dir)
            with open(os.path.join(git_dir, "config.py"), "w") as f:
                f.write("ignored\n")

            # Create valid file
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write("valid\n")

            bundler = LogosBundler(root_path=tmpdir)
            bundle_bytes, _ = bundler.create_bundle()

            buf = io.BytesIO(bundle_bytes)
            with tarfile.open(fileobj=buf, mode="r:gz") as tar:
                names = tar.getnames()
                self.assertEqual(len(names), 1)
                self.assertIn("main.py", names)

    def test_create_bundle_nested_dirs(self):
        """Test bundle creation with nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "src", "module")
            os.makedirs(nested)
            with open(os.path.join(nested, "core.py"), "w") as f:
                f.write("# nested file\n")

            bundler = LogosBundler(root_path=tmpdir)
            bundle_bytes, _ = bundler.create_bundle()

            buf = io.BytesIO(bundle_bytes)
            with tarfile.open(fileobj=buf, mode="r:gz") as tar:
                names = tar.getnames()
                self.assertIn("src/module/core.py", names)

    def test_create_bundle_permission_error(self):
        """Test handling of permission errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("content\n")

            bundler = LogosBundler(root_path=tmpdir)

            # Mock open to raise PermissionError
            with patch("builtins.open", side_effect=PermissionError("denied")):
                # Should not raise, just skip the file
                bundle_bytes, _ = bundler.create_bundle()
                self.assertIsInstance(bundle_bytes, bytes)


class TestSafeExtractFilter(unittest.TestCase):
    """Test path traversal protection."""

    def setUp(self):
        self.bundler = LogosBundler()

    def test_filter_rejects_absolute_path_unix(self):
        """Test rejection of absolute Unix paths."""
        member = MagicMock()
        member.name = "/etc/passwd"
        member.issym.return_value = False
        member.islnk.return_value = False

        result = self.bundler._safe_extract_filter(member, "/tmp")
        self.assertIsNone(result)

    def test_filter_rejects_absolute_path_windows(self):
        """Test rejection of absolute Windows paths."""
        member = MagicMock()
        member.name = "\\Windows\\System32"
        member.issym.return_value = False
        member.islnk.return_value = False

        result = self.bundler._safe_extract_filter(member, "/tmp")
        self.assertIsNone(result)

    def test_filter_rejects_path_traversal(self):
        """Test rejection of path traversal attempts."""
        member = MagicMock()
        member.name = "../../../etc/passwd"
        member.issym.return_value = False
        member.islnk.return_value = False

        result = self.bundler._safe_extract_filter(member, "/tmp")
        self.assertIsNone(result)

    def test_filter_rejects_symlinks(self):
        """Test rejection of symbolic links."""
        member = MagicMock()
        member.name = "link.py"
        member.issym.return_value = True
        member.islnk.return_value = False

        result = self.bundler._safe_extract_filter(member, "/tmp")
        self.assertIsNone(result)

    def test_filter_rejects_hardlinks(self):
        """Test rejection of hard links."""
        member = MagicMock()
        member.name = "hardlink.py"
        member.issym.return_value = False
        member.islnk.return_value = True

        result = self.bundler._safe_extract_filter(member, "/tmp")
        self.assertIsNone(result)

    def test_filter_accepts_valid_path(self):
        """Test acceptance of valid paths."""
        member = MagicMock()
        member.name = "src/module/file.py"
        member.issym.return_value = False
        member.islnk.return_value = False

        result = self.bundler._safe_extract_filter(member, "/tmp")
        self.assertEqual(result, member)


class TestUnpackBundle(unittest.TestCase):
    """Test bundle unpacking."""

    def test_unpack_bundle_success(self):
        """Test successful bundle unpacking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a bundle
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "test.py"), "w") as f:
                f.write("# test content\n")

            bundler = LogosBundler(root_path=src_dir)
            bundle_bytes, _ = bundler.create_bundle()

            # Unpack to different directory
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(dest_dir)
            bundler.unpack_bundle(bundle_bytes, dest_dir)

            # Verify extraction
            unpacked_file = os.path.join(dest_dir, "test.py")
            self.assertTrue(os.path.exists(unpacked_file))
            with open(unpacked_file) as f:
                self.assertEqual(f.read(), "# test content\n")

    def test_unpack_bundle_filters_malicious(self):
        """Test that malicious entries are filtered during unpack."""
        # Create a malicious tarball manually
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            # Add a normal file
            info = tarfile.TarInfo(name="normal.py")
            content = b"# normal file\n"
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

            # Add a path traversal attempt
            info2 = tarfile.TarInfo(name="../../../etc/passwd")
            content2 = b"malicious\n"
            info2.size = len(content2)
            tar.addfile(info2, io.BytesIO(content2))

        bundle_bytes = buf.getvalue()

        with tempfile.TemporaryDirectory() as tmpdir:
            bundler = LogosBundler()
            bundler.unpack_bundle(bundle_bytes, tmpdir)

            # Normal file should exist
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "normal.py")))
            # Traversal file should NOT exist
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "..", "etc")))


class TestSignAndVerify(unittest.TestCase):
    """Test bundle signing and verification."""

    @patch("warm_logic.kernel.autonomy.bundle.SovereignSecurity")
    def test_sign_bundle(self, mock_security):
        """Test bundle signing."""
        mock_security.sign.return_value = "signature123456789abcdef"

        bundler = LogosBundler()
        signature = bundler.sign_bundle("private_key", "manifest_hash")

        mock_security.sign.assert_called_once_with("private_key", "manifest_hash")
        self.assertEqual(signature, "signature123456789abcdef")

    @patch("warm_logic.kernel.autonomy.bundle.SovereignSecurity")
    def test_verify_bundle_valid(self, mock_security):
        """Test successful signature verification."""
        mock_security.verify.return_value = True

        bundler = LogosBundler()
        result = bundler.verify_bundle("public_key", "manifest_hash", "signature")

        mock_security.verify.assert_called_once_with(
            "public_key", "manifest_hash", "signature"
        )
        self.assertTrue(result)

    @patch("warm_logic.kernel.autonomy.bundle.SovereignSecurity")
    def test_verify_bundle_invalid(self, mock_security):
        """Test failed signature verification."""
        mock_security.verify.return_value = False

        bundler = LogosBundler()
        result = bundler.verify_bundle("public_key", "manifest_hash", "bad_sig")

        self.assertFalse(result)


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests."""

    def test_create_unpack_roundtrip(self):
        """Test full create -> unpack cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create multiple files
            files = {
                "main.py": "# main\n",
                "lib.rs": "// rust\n",
                "config.toml": "[config]\n",
                "README.md": "# Readme\n",
            }
            for name, content in files.items():
                with open(os.path.join(src_dir, name), "w") as f:
                    f.write(content)

            # Bundle and unpack
            bundler = LogosBundler(root_path=src_dir)
            bundle_bytes, manifest_hash = bundler.create_bundle()
            bundler.unpack_bundle(bundle_bytes, dest_dir)

            # Verify all files
            for name, expected_content in files.items():
                path = os.path.join(dest_dir, name)
                self.assertTrue(os.path.exists(path), f"{name} should exist")
                with open(path) as f:
                    self.assertEqual(f.read(), expected_content)


if __name__ == "__main__":
    unittest.main()
