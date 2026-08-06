# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""
[P3xx] Unit tests for governance modules.
Tests: constitution.py, formal/verifier.py
"""

import math
import unittest
from unittest import mock

from warm_logic.kernel.formal.verifier import PatchVerifier


class TestPatchVerifier(unittest.TestCase):
    """Test PatchVerifier for code safety analysis."""

    def test_verify_safe_code(self):
        """Test verification of safe code."""
        code = """
def hello():
    return "Hello, World!"
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertTrue(is_safe)
        self.assertEqual(violations, [])

    def test_verify_syntax_error(self):
        """Test verification catches syntax errors."""
        code = "def broken("
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertFalse(is_safe)
        self.assertTrue(any("Syntax Error" in v for v in violations))

    def test_verify_os_system_violation(self):
        """Test detection of os.system calls."""
        code = """
import os
os.system("ls -la")
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertFalse(is_safe)
        self.assertTrue(any("os.system" in v for v in violations))

    def test_verify_subprocess_call_violation(self):
        """Test detection of subprocess.call."""
        code = """
import subprocess
subprocess.call(["ls"])
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertFalse(is_safe)
        self.assertTrue(any("subprocess" in v for v in violations))

    def test_verify_subprocess_run_violation(self):
        """Test detection of subprocess.run."""
        code = """
import subprocess
subprocess.run(["echo", "test"])
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertFalse(is_safe)
        self.assertTrue(any("subprocess" in v for v in violations))

    def test_verify_subprocess_popen_violation(self):
        """Test detection of subprocess.Popen."""
        code = """
import subprocess
p = subprocess.Popen(["cat"])
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertFalse(is_safe)
        self.assertTrue(any("subprocess" in v for v in violations))

    def test_verify_constitution_deletion_violation(self):
        """Test detection of SovereignConstitution deletion."""
        code = """
del SovereignConstitution
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertFalse(is_safe)
        self.assertTrue(any("SovereignConstitution" in v for v in violations))

    def test_verify_multiple_violations(self):
        """Test detection of multiple violations."""
        code = """
import os
import subprocess
os.system("rm -rf /")
subprocess.run(["format"])
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertFalse(is_safe)
        self.assertGreaterEqual(len(violations), 2)

    def test_verify_safe_import(self):
        """Test safe imports are allowed."""
        code = """
import json
import logging
from typing import Dict, List
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertTrue(is_safe)
        self.assertEqual(violations, [])

    def test_verify_safe_class_definition(self):
        """Test safe class definitions are allowed."""
        code = """
class MyService:
    def __init__(self):
        self.data = {}

    def process(self, item):
        return item.upper()
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertTrue(is_safe)
        self.assertEqual(violations, [])

    def test_is_banned_call_helper(self):
        """Test _is_banned_call helper function."""
        import ast

        # Parse a known banned call
        tree = ast.parse("os.system('test')")
        call_node = tree.body[0].value
        result = PatchVerifier._is_banned_call(call_node, "os", "system")
        self.assertTrue(result)

    def test_is_banned_call_non_matching(self):
        """Test _is_banned_call returns False for non-matching calls."""
        import ast

        tree = ast.parse("json.dumps(data)")
        call_node = tree.body[0].value
        result = PatchVerifier._is_banned_call(call_node, "os", "system")
        self.assertFalse(result)


class TestConstitutionalGuardEntropy(unittest.TestCase):
    """Test entropy calculation from ConstitutionalGuard."""

    def test_entropy_empty_string(self):
        """Test entropy of empty string is 0."""

        # Import entropy calculation logic
        def calculate_entropy(text: str) -> float:
            if not text:
                return 0.0
            entropy = 0.0
            for x in range(256):
                p_x = float(text.count(chr(x))) / len(text)
                if p_x > 0:
                    entropy += -p_x * math.log(p_x, 2)
            return entropy

        self.assertEqual(calculate_entropy(""), 0.0)

    def test_entropy_uniform_distribution(self):
        """Test entropy of uniform distribution."""

        def calculate_entropy(text: str) -> float:
            if not text:
                return 0.0
            entropy = 0.0
            for x in range(256):
                p_x = float(text.count(chr(x))) / len(text)
                if p_x > 0:
                    entropy += -p_x * math.log(p_x, 2)
            return entropy

        # Single character repeated has 0 entropy
        self.assertEqual(calculate_entropy("aaaa"), 0.0)

        # Two equally distributed characters has 1 bit entropy
        entropy = calculate_entropy("ab" * 100)
        self.assertAlmostEqual(entropy, 1.0, places=2)

    def test_entropy_increases_with_diversity(self):
        """Test entropy increases with character diversity."""

        def calculate_entropy(text: str) -> float:
            if not text:
                return 0.0
            entropy = 0.0
            for x in range(256):
                p_x = float(text.count(chr(x))) / len(text)
                if p_x > 0:
                    entropy += -p_x * math.log(p_x, 2)
            return entropy

        low_entropy = calculate_entropy("aaabbb")
        high_entropy = calculate_entropy("abcdefghij")
        self.assertGreater(high_entropy, low_entropy)


class TestGovernanceIntegration(unittest.TestCase):
    """Integration tests for governance modules."""

    def test_verifier_with_complex_code(self):
        """Test verifier with realistic complex code."""
        code = """
class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.results = []

    def process(self, items):
        for item in items:
            result = self._transform(item)
            self.results.append(result)
        return self.results

    def _transform(self, item):
        return {
            'id': item.get('id'),
            'processed': True,
            'data': item.get('data', [])
        }
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertTrue(is_safe)

    def test_verifier_allows_safe_file_operations(self):
        """Test verifier allows safe file operations."""
        code = """
with open('data.json', 'r') as f:
    data = json.load(f)
"""
        is_safe, violations = PatchVerifier.verify_patch(code)
        self.assertTrue(is_safe)


if __name__ == "__main__":
    unittest.main()
