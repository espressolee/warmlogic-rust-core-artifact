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
Constitution Coverage Tests - Phase 3
Covers: apply_amendment, UpdateSafetyAxiom, SovereignKillpulseAxiom
"""

import tempfile
from pathlib import Path
from unittest import mock


from warm_logic.kernel.constitution import (
    ConstitutionalGuard,
    SovereignKillpulseAxiom,
    UpdateSafetyAxiom,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestApplyAmendment(WarmLogicTestCase):
    """Tests for ConstitutionalGuard.apply_amendment method."""

    def setUp(self):
        super().setUp()
        # Create a guard with mocked constitution
        with mock.patch(
            "warm_logic.kernel.constitution.Path.exists", return_value=False
        ):
            self.guard = ConstitutionalGuard()
        self.guard.constitution = {"defense_level": 100}

    def test_apply_amendment_missing_signature(self):
        """Amendment should be rejected without quorum signature."""
        result = self.guard.apply_amendment({"new_rule": "value"}, "")
        self.assertFalse(result)

    def test_apply_amendment_null_signature(self):
        """Amendment should be rejected with None signature."""
        result = self.guard.apply_amendment({"new_rule": "value"}, None)
        self.assertFalse(result)

    def test_apply_amendment_success(self):
        """Amendment should succeed with valid quorum signature."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        with mock.patch("warm_logic.kernel.constitution.CONSTITUTION_PATH", temp_path):
            result = self.guard.apply_amendment(
                {"new_rule": "value", "defense_level": 80},
                "BFT_QUORUM_SIG_2F3",
            )
            self.assertTrue(result)
            self.assertEqual(self.guard.constitution["new_rule"], "value")
            self.assertEqual(self.guard.constitution["defense_level"], 80)

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_apply_amendment_creates_constitution_if_none(self):
        """Amendment should create constitution dict if None."""
        self.guard.constitution = None
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        with mock.patch("warm_logic.kernel.constitution.CONSTITUTION_PATH", temp_path):
            result = self.guard.apply_amendment({"new_rule": "value"}, "BFT_QUORUM_SIG")
            self.assertTrue(result)
            self.assertIsNotNone(self.guard.constitution)

        Path(temp_path).unlink(missing_ok=True)

    def test_apply_amendment_disk_failure(self):
        """Amendment should handle disk write failure gracefully."""
        with mock.patch(
            "warm_logic.kernel.constitution.CONSTITUTION_PATH",
            "/invalid/path/constitution.yaml",
        ):
            result = self.guard.apply_amendment({"new_rule": "value"}, "BFT_QUORUM_SIG")
            self.assertFalse(result)


class TestSanitizeEdgeCases(WarmLogicTestCase):
    """Additional edge case tests for sanitize."""

    def test_sanitize_without_constitution_raises(self):
        """Sanitize should raise RuntimeError if constitution is None."""
        with mock.patch(
            "warm_logic.kernel.constitution.Path.exists", return_value=False
        ):
            guard = ConstitutionalGuard()
        guard.constitution = None

        with self.assertRaises(RuntimeError) as ctx:
            guard.sanitize("test text")
        self.assertIn("Constitution not loaded", str(ctx.exception))


class TestUpdateSafetyAxiom(WarmLogicTestCase):
    """Tests for UpdateSafetyAxiom.verify_update method."""

    def test_invalid_magic_bytes(self):
        """Patch should be rejected without magic bytes."""
        patch_data = b"INVALID_PATCH_DATA"
        result = UpdateSafetyAxiom.verify_update(patch_data)
        self.assertFalse(result)

    def test_oversized_patch(self):
        """Patch should be rejected if larger than 5MB."""
        # Create a patch with valid magic bytes but too large
        patch_data = b"\x7fWL_PATCH" + b"x" * (6 * 1024 * 1024)
        result = UpdateSafetyAxiom.verify_update(patch_data)
        self.assertFalse(result)

    def test_missing_pqc_signature(self):
        """Patch should be rejected without PQC signature marker."""
        patch_data = b"\x7fWL_PATCH" + b"valid_content_no_sig"
        result = UpdateSafetyAxiom.verify_update(patch_data)
        self.assertFalse(result)

    def test_valid_patch(self):
        """Valid patch should be accepted."""
        patch_data = (
            b"\x7fWL_PATCH"
            + b"valid_content"
            + b"---PQC_SIG_BEGIN---"
            + b"signature_data"
        )
        result = UpdateSafetyAxiom.verify_update(patch_data)
        self.assertTrue(result)

    def test_empty_patch(self):
        """Empty patch should be rejected."""
        result = UpdateSafetyAxiom.verify_update(b"")
        self.assertFalse(result)


class TestSovereignKillpulseAxiom(WarmLogicTestCase):
    """Tests for SovereignKillpulseAxiom.verify_killpulse method."""

    def test_valid_killpulse(self):
        """Valid PANIC_STOP with correct signature should be verified."""
        result = SovereignKillpulseAxiom.verify_killpulse(
            b"PANIC_STOP", "ROOT_AUTHORITY_SIG_0xDEADBEEF"
        )
        self.assertTrue(result)

    def test_invalid_signal(self):
        """Invalid signal should not be verified."""
        result = SovereignKillpulseAxiom.verify_killpulse(
            b"INVALID_SIGNAL", "ROOT_AUTHORITY_SIG_0xDEADBEEF"
        )
        self.assertFalse(result)

    def test_invalid_signature(self):
        """Valid signal with invalid signature should not be verified."""
        result = SovereignKillpulseAxiom.verify_killpulse(
            b"PANIC_STOP", "INVALID_SIGNATURE"
        )
        self.assertFalse(result)

    def test_empty_signal(self):
        """Empty signal should not be verified."""
        result = SovereignKillpulseAxiom.verify_killpulse(b"", "")
        self.assertFalse(result)
