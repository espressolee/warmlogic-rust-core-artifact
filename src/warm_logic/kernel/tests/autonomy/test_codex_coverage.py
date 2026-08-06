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
Comprehensive tests for autonomy/codex.py - SovereignCodebase
Target: 80%+ coverage
"""

import os
import tempfile
import unittest

from warm_logic.kernel.autonomy.codex import LogicGap, SovereignCodebase


class TestLogicGap(unittest.TestCase):
    """Test LogicGap dataclass."""

    def test_logic_gap_creation(self):
        """Test basic LogicGap creation."""
        gap = LogicGap(
            file_path="/test/file.py",
            line_number=42,
            description="Test gap",
            gap_type="TODO",
        )
        self.assertEqual(gap.file_path, "/test/file.py")
        self.assertEqual(gap.line_number, 42)
        self.assertEqual(gap.description, "Test gap")
        self.assertEqual(gap.gap_type, "TODO")
        self.assertEqual(gap.priority, 50)  # default
        self.assertEqual(gap.complexity, 1)  # default

    def test_logic_gap_with_custom_priority(self):
        """Test LogicGap with custom priority."""
        gap = LogicGap(
            file_path="/test.py",
            line_number=1,
            description="High priority",
            gap_type="NotImplemented",
            priority=90,
            complexity=5,
        )
        self.assertEqual(gap.priority, 90)
        self.assertEqual(gap.complexity, 5)

    def test_logic_gap_frozen(self):
        """Test that LogicGap is immutable (frozen)."""
        gap = LogicGap(
            file_path="/test.py",
            line_number=1,
            description="Test",
            gap_type="TODO",
        )
        with self.assertRaises(Exception):  # FrozenInstanceError
            gap.line_number = 99


class TestSovereignCodebaseInit(unittest.TestCase):
    """Test SovereignCodebase initialization."""

    def test_init_default_path(self):
        """Test initialization with default path."""
        codex = SovereignCodebase()
        self.assertEqual(codex.root_path, os.path.abspath("."))
        self.assertIn(".git", codex.ignore_dirs)
        self.assertIn("__pycache__", codex.ignore_dirs)

    def test_init_custom_path(self):
        """Test initialization with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            codex = SovereignCodebase(root_path=tmpdir)
            self.assertEqual(codex.root_path, tmpdir)


class TestAnalyzeFile(unittest.TestCase):
    """Test file analysis for gaps."""

    def test_detect_not_implemented_error_simple(self):
        """Test detection of raise NotImplementedError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("""
def incomplete():
    raise NotImplementedError
""")
            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex._analyze_file(test_file)

            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0].gap_type, "NotImplemented")
            self.assertEqual(gaps[0].line_number, 3)

    def test_detect_not_implemented_error_with_message(self):
        """Test detection of raise NotImplementedError('msg')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("""
def incomplete():
    raise NotImplementedError("Need to implement X")
""")
            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex._analyze_file(test_file)

            self.assertEqual(len(gaps), 1)
            self.assertIn("Need to implement X", gaps[0].description)

    def test_detect_todo_comments(self):
        """Test detection of TODO comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("""
# TODO: Fix this later
def complete():
    pass  # TODO: Add validation
""")
            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex._analyze_file(test_file)

            todo_gaps = [g for g in gaps if g.gap_type == "TODO"]
            self.assertEqual(len(todo_gaps), 2)

    def test_detect_mixed_gaps(self):
        """Test detection of mixed NotImplemented and TODO."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("""
# TODO: Refactor this
def incomplete():
    raise NotImplementedError("Future work")

# TODO: Add tests
""")
            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex._analyze_file(test_file)

            self.assertEqual(len(gaps), 3)

    def test_syntax_error_handling(self):
        """Test handling of files with syntax errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "broken.py")
            with open(test_file, "w") as f:
                f.write("""
def broken(
    # Missing closing paren
# TODO: This should still be found
""")
            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex._analyze_file(test_file)

            # TODO should still be detected even with syntax error
            todo_gaps = [g for g in gaps if g.gap_type == "TODO"]
            self.assertGreaterEqual(len(todo_gaps), 1)

    def test_read_error_handling(self):
        """Test handling of unreadable files."""
        codex = SovereignCodebase()
        # Non-existent file
        gaps = codex._analyze_file("/nonexistent/path/file.py")
        self.assertEqual(gaps, [])

    def test_raise_without_exception(self):
        """Test handling of bare raise statements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("""
def reraise():
    try:
        pass
    except:
        raise  # bare raise, no exception
""")
            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex._analyze_file(test_file)
            # Should not crash, bare raise should be ignored
            not_impl = [g for g in gaps if g.gap_type == "NotImplemented"]
            self.assertEqual(len(not_impl), 0)


class TestScanCodebase(unittest.TestCase):
    """Test full codebase scanning."""

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex.scan_codebase()
            self.assertEqual(gaps, [])

    def test_scan_with_files(self):
        """Test scanning directory with Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write("# TODO: Entry point\n")

            with open(os.path.join(tmpdir, "lib.py"), "w") as f:
                f.write("def stub(): raise NotImplementedError\n")

            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex.scan_codebase()

            self.assertEqual(len(gaps), 2)

    def test_scan_ignores_directories(self):
        """Test that ignored directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create ignored directory
            git_dir = os.path.join(tmpdir, ".git")
            os.makedirs(git_dir)
            with open(os.path.join(git_dir, "ignored.py"), "w") as f:
                f.write("# TODO: Should be ignored\n")

            # Create valid file
            with open(os.path.join(tmpdir, "valid.py"), "w") as f:
                f.write("# TODO: Should be found\n")

            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex.scan_codebase()

            self.assertEqual(len(gaps), 1)
            self.assertIn("valid.py", gaps[0].file_path)

    def test_scan_nested_directories(self):
        """Test scanning nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "src", "module")
            os.makedirs(nested)

            with open(os.path.join(nested, "core.py"), "w") as f:
                f.write("# TODO: Implement core logic\n")

            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex.scan_codebase()

            self.assertEqual(len(gaps), 1)
            self.assertIn("core.py", gaps[0].file_path)

    def test_scan_only_python_files(self):
        """Test that only .py files are analyzed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Non-Python files
            with open(os.path.join(tmpdir, "config.yaml"), "w") as f:
                f.write("# TODO: Should be ignored\n")

            with open(os.path.join(tmpdir, "readme.md"), "w") as f:
                f.write("# TODO: Should be ignored\n")

            # Python file
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write("# TODO: Should be found\n")

            codex = SovereignCodebase(root_path=tmpdir)
            gaps = codex.scan_codebase()

            self.assertEqual(len(gaps), 1)


class TestProposeBackfill(unittest.TestCase):
    """Test backfill proposal generation."""

    def test_propose_backfill(self):
        """Test proposal generation."""
        codex = SovereignCodebase()
        gap = LogicGap(
            file_path="/test/file.py",
            line_number=42,
            description="Missing implementation",
            gap_type="NotImplemented",
        )

        proposal = codex.propose_backfill(gap)

        self.assertIn("PLAN:", proposal)
        self.assertIn("NotImplemented", proposal)
        self.assertIn("/test/file.py", proposal)
        self.assertIn("42", proposal)

    def test_propose_backfill_todo(self):
        """Test proposal for TODO gap."""
        codex = SovereignCodebase()
        gap = LogicGap(
            file_path="/src/module.py",
            line_number=100,
            description="# TODO: Add validation",
            gap_type="TODO",
        )

        proposal = codex.propose_backfill(gap)

        self.assertIn("TODO", proposal)


if __name__ == "__main__":
    unittest.main()
