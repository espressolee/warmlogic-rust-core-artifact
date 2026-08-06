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
Comprehensive tests for autonomy/aegis.py - Security Auditing
Target: 80%+ coverage
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.autonomy.aegis import (
    AegisAuditor,
    AegisGuard,
    AegisSentinel,
    Vulnerability,
)
from warm_logic.kernel.autonomy.codex import LogicGap


class TestVulnerability(unittest.TestCase):
    """Test Vulnerability dataclass."""

    def test_vulnerability_creation(self):
        """Test basic vulnerability creation."""
        vuln = Vulnerability(
            file_path="/test/file.py",
            line_number=42,
            description="Test vulnerability",
            vulnerability_type="security_vulnerability",
        )
        self.assertEqual(vuln.file_path, "/test/file.py")
        self.assertEqual(vuln.line_number, 42)
        self.assertEqual(vuln.description, "Test vulnerability")
        self.assertEqual(vuln.vulnerability_type, "security_vulnerability")


class TestAegisAuditor(unittest.TestCase):
    """Test AegisAuditor security scanning."""

    def test_auditor_init(self):
        """Test auditor initialization."""
        auditor = AegisAuditor()
        self.assertEqual(auditor.root_path, os.path.abspath("."))

    def test_auditor_init_custom_path(self):
        """Test auditor with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            auditor = AegisAuditor(root_path=tmpdir)
            self.assertEqual(auditor.root_path, tmpdir)

    def test_audit_file_detects_eval(self):
        """Test detection of unsafe eval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "unsafe.py")
            with open(test_file, "w") as f:
                f.write("result = eval(user_input)\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = auditor._audit_file(test_file)

            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0].gap_type, "security_vulnerability")
            self.assertIn("eval", gaps[0].description)

    def test_audit_file_detects_exec(self):
        """Test detection of unsafe exec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "unsafe.py")
            with open(test_file, "w") as f:
                f.write("exec(code_string)\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = auditor._audit_file(test_file)

            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0].gap_type, "security_vulnerability")
            self.assertIn("exec", gaps[0].description)

    def test_audit_file_detects_hardcoded_secret(self):
        """Test detection of hardcoded secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "secrets.py")
            with open(test_file, "w") as f:
                # Use variable name that triggers detection (api_key)
                f.write("api_key = 'test_value_for_detection'\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = auditor._audit_file(test_file)

            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0].gap_type, "hardcoded_secret")

    def test_audit_file_detects_password(self):
        """Test detection of hardcoded password."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "secrets.py")
            with open(test_file, "w") as f:
                # Use variable name that triggers detection (password)
                f.write("db_password = 'test_pw_value'\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = auditor._audit_file(test_file)

            self.assertEqual(len(gaps), 1)
            self.assertIn("password", gaps[0].description.lower())

    def test_audit_file_detects_token(self):
        """Test detection of hardcoded token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "secrets.py")
            with open(test_file, "w") as f:
                # Use variable name that triggers detection (token)
                f.write("auth_token = 'test_tok_value'\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = auditor._audit_file(test_file)

            self.assertEqual(len(gaps), 1)

    def test_audit_file_safe_code(self):
        """Test that safe code produces no gaps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "safe.py")
            with open(test_file, "w") as f:
                f.write("def add(a, b):\n    return a + b\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = auditor._audit_file(test_file)

            self.assertEqual(len(gaps), 0)

    def test_audit_file_syntax_error(self):
        """Test handling of syntax errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "broken.py")
            with open(test_file, "w") as f:
                f.write("def broken(\n")  # Syntax error

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = auditor._audit_file(test_file)

            self.assertEqual(gaps, [])

    def test_audit_file_nonexistent(self):
        """Test handling of non-existent file."""
        auditor = AegisAuditor()
        gaps = auditor._audit_file("/nonexistent/file.py")
        self.assertEqual(gaps, [])

    def test_audit_file_multiple_issues(self):
        """Test detection of multiple issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "multi.py")
            with open(test_file, "w") as f:
                # Use variable name that triggers detection (secret)
                f.write("secret = 'test_sec_value'\n")
                f.write("result = eval(user_input)\n")
                f.write("exec(code)\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = auditor._audit_file(test_file)

            self.assertEqual(len(gaps), 3)


class TestAegisAuditorAsync(unittest.TestCase):
    """Test AegisAuditor async methods."""

    def test_audit_codebase(self):
        """Test full codebase audit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file = os.path.join(tmpdir, "unsafe.py")
            with open(test_file, "w") as f:
                f.write("eval(x)\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = asyncio.run(auditor.audit_codebase())

            self.assertGreaterEqual(len(gaps), 1)

    def test_audit_codebase_skips_git(self):
        """Test that .git directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .git directory with unsafe code
            git_dir = os.path.join(tmpdir, ".git")
            os.makedirs(git_dir)
            with open(os.path.join(git_dir, "unsafe.py"), "w") as f:
                f.write("eval(x)\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = asyncio.run(auditor.audit_codebase())

            self.assertEqual(len(gaps), 0)

    def test_audit_codebase_skips_venv(self):
        """Test that .venv directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .venv directory with unsafe code
            venv_dir = os.path.join(tmpdir, ".venv")
            os.makedirs(venv_dir)
            with open(os.path.join(venv_dir, "unsafe.py"), "w") as f:
                f.write("eval(x)\n")

            auditor = AegisAuditor(root_path=tmpdir)
            gaps = asyncio.run(auditor.audit_codebase())

            self.assertEqual(len(gaps), 0)


class TestAegisSentinel(unittest.TestCase):
    """Test AegisSentinel security monitoring."""

    def test_sentinel_init(self):
        """Test sentinel initialization."""
        auditor = AegisAuditor()
        sentinel = AegisSentinel(auditor)
        self.assertIs(sentinel.auditor, auditor)

    def test_secure_perimeter(self):
        """Test perimeter security scan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "vuln.py")
            with open(test_file, "w") as f:
                f.write("eval(user_input)\n")

            auditor = AegisAuditor(root_path=tmpdir)
            sentinel = AegisSentinel(auditor)
            vulns = asyncio.run(sentinel.secure_perimeter())

            self.assertGreaterEqual(len(vulns), 1)
            self.assertIsInstance(vulns[0], Vulnerability)
            self.assertEqual(vulns[0].vulnerability_type, "security_vulnerability")

    def test_validate_patch_safe(self):
        """Test validation of safe patch."""
        auditor = AegisAuditor()
        sentinel = AegisSentinel(auditor)

        safe_code = "def safe_function(x):\n    return x * 2\n"
        result = sentinel.validate_patch(
            LogicGap("/test.py", 1, "test", "TODO"), safe_code
        )

        self.assertTrue(result)

    def test_validate_patch_rejects_eval(self):
        """Test validation rejects eval."""
        auditor = AegisAuditor()
        sentinel = AegisSentinel(auditor)

        unsafe_code = "def fix():\n    return eval(user_input)\n"
        result = sentinel.validate_patch(
            LogicGap("/test.py", 1, "test", "TODO"), unsafe_code
        )

        self.assertFalse(result)

    def test_validate_patch_rejects_exec(self):
        """Test validation rejects exec."""
        auditor = AegisAuditor()
        sentinel = AegisSentinel(auditor)

        unsafe_code = "def fix():\n    exec(code)\n"
        result = sentinel.validate_patch(
            LogicGap("/test.py", 1, "test", "TODO"), unsafe_code
        )

        self.assertFalse(result)

    def test_validate_patch_syntax_error(self):
        """Test validation handles syntax errors."""
        auditor = AegisAuditor()
        sentinel = AegisSentinel(auditor)

        broken_code = "def broken(\n"  # Syntax error
        result = sentinel.validate_patch(
            LogicGap("/test.py", 1, "test", "TODO"), broken_code
        )

        self.assertFalse(result)


class TestAegisGuard(unittest.TestCase):
    """Test AegisGuard mutation verification."""

    def test_guard_init(self):
        """Test guard initialization."""
        guard = AegisGuard()
        self.assertEqual(guard.root_path, os.path.abspath("."))

    def test_guard_init_custom_path(self):
        """Test guard with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            guard = AegisGuard(root_path=tmpdir)
            self.assertEqual(guard.root_path, tmpdir)

    def test_verify_mutation_success(self):
        """Test successful mutation verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create tests/autonomy directory
            test_dir = os.path.join(tmpdir, "tests", "autonomy")
            os.makedirs(test_dir, exist_ok=True)

            guard = AegisGuard(root_path=tmpdir)

            patch_code = "def add(a, b):\n    return a + b\n"
            test_code = """
def test_add():
    assert True
"""

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                result = asyncio.run(
                    guard.verify_mutation("/test.py", "add", patch_code, test_code)
                )

            self.assertTrue(result)

    def test_verify_mutation_failure(self):
        """Test failed mutation verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "tests", "autonomy")
            os.makedirs(test_dir, exist_ok=True)

            guard = AegisGuard(root_path=tmpdir)

            patch_code = "def broken():\n    pass\n"
            test_code = """
def test_broken():
    assert False
"""

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1, stdout="FAILED", stderr=""
                )
                result = asyncio.run(
                    guard.verify_mutation("/test.py", "broken", patch_code, test_code)
                )

            self.assertFalse(result)

    def test_verify_mutation_exception(self):
        """Test mutation verification with exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "tests", "autonomy")
            os.makedirs(test_dir, exist_ok=True)

            guard = AegisGuard(root_path=tmpdir)

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Test error")
                result = asyncio.run(
                    guard.verify_mutation("/test.py", "error", "code", "test_code")
                )

            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
