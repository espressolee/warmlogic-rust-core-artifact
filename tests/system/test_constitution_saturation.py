import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from warm_logic.kernel.constitution import (
    ConstitutionalGuard,
    UpdateSafetyAxiom,
    constitutional_audit,
)


class TestConstitutionSaturation:
    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return tmp_path

    def test_load_constitution_missing(self, tmp_dir):
        with patch(
            "warm_logic.kernel.constitution.CONSTITUTION_PATH", tmp_dir / "none.yaml"
        ):
            guard = ConstitutionalGuard()
            assert guard.constitution is None

    def test_load_constitution_success_mock(self, tmp_dir):
        # Force reload with patched dependencies
        path = tmp_dir / "signed_const.yaml"
        path.write_text(yaml.dump({"data": {"a": 1}, "signature": "hex"}))
        with patch("warm_logic.kernel.constitution.CONSTITUTION_PATH", path):
            guard = ConstitutionalGuard()
            with patch.object(guard, "_verify", return_value=True):
                guard.load_constitution()
                assert guard.constitution == {"a": 1}

    def test_load_constitution_error(self, tmp_dir):
        path = tmp_dir / "error.yaml"
        # Triggers exception during yaml load
        path.write_text("!!python/object:non_existent.Class {}")
        with patch("warm_logic.kernel.constitution.CONSTITUTION_PATH", path):
            guard = ConstitutionalGuard()
            # The exception is caught in load_constitution
            guard.load_constitution()
            assert guard.constitution is None

    def test_verify_missing_key(self, tmp_dir):
        guard = ConstitutionalGuard()
        with patch("warm_logic.kernel.constitution.PUB_KEY_PATH", tmp_dir / "no_key"):
            assert guard._verify({}) is False

    def test_verify_exception(self, tmp_dir):
        guard = ConstitutionalGuard()
        with patch("warm_logic.kernel.constitution.PUB_KEY_PATH", tmp_dir / "key"):
            (tmp_dir / "key").write_text("not_b64")
            assert guard._verify({}) is False

    def test_verify_success_mocked(self, tmp_dir):
        guard = ConstitutionalGuard()
        key_path = tmp_dir / "key.dat"
        key_path.write_bytes(base64.b64encode(b"fake_pub_key"))
        with patch("warm_logic.kernel.constitution.PUB_KEY_PATH", key_path):
            with patch(
                "cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey.from_public_bytes"
            ) as mock_from:
                mock_key = mock_from.return_value
                signed_data = {"data": {"a": 1}, "signature": "00" * 32}
                assert guard._verify(signed_data) is True
                # Hit the verify path
                mock_key.verify.assert_called()

    def test_calculate_entropy_edge(self):
        # We need a new instance because the global one might have a loaded constitution
        guard = ConstitutionalGuard()
        assert guard.calculate_entropy("") == 0.0
        # High entropy string
        res = guard.calculate_entropy("abcdefghijklmnopqrstuvwxyz1234567890")
        assert res > 2.0

    def test_sanitize_no_constitution(self):
        guard = ConstitutionalGuard()
        guard.constitution = None
        with pytest.raises(RuntimeError, match="Constitution not loaded"):
            guard.sanitize("test")

    def test_sanitize_flow(self):
        guard = ConstitutionalGuard()
        # 1. No law, no operation path
        guard.constitution = None
        with pytest.raises(RuntimeError):
            guard.sanitize("abc")

        # 2. Success path with keyword violations (high entropy threshold to avoid block)
        guard.constitution = {
            "sensitive_keywords": ["SECRET"],
            "entropy_threshold": 10.0,  # High threshold to not trigger entropy block
            "defense_level": 100,
        }

        # Keyword Redaction
        text, violations = guard.sanitize("This is a SECRET")
        assert "[REDACTED_BY_CONSTITUTION]" in text
        assert violations >= 1

        # 3. Entropy blocking test (low threshold)
        guard.constitution = {
            "sensitive_keywords": [],
            "entropy_threshold": 1.0,  # Low threshold to trigger entropy block
            "defense_level": 100,
        }
        text, violations = guard.sanitize("This is a test message")
        assert "OUTPUT BLOCKED" in text
        assert violations >= 1

    def test_sanitize_low_defense(self):
        guard = ConstitutionalGuard()
        guard.constitution = {
            "sensitive_keywords": [],
            "entropy_threshold": 0.1,
            "defense_level": 10,  # Should not block output
        }
        text, violations = guard.sanitize("High Entropy")
        assert text == "High Entropy"  # Not blocked
        assert violations == 0

    def test_apply_amendment(self, tmp_dir):
        guard = ConstitutionalGuard()
        guard.constitution = None

        # 1. No signature
        assert guard.apply_amendment({"new": 2}, "") is False

        # 2. Success path starts from None constitution (line 128)
        amendment_path = tmp_dir / "const.yaml"
        with patch("warm_logic.kernel.constitution.CONSTITUTION_PATH", amendment_path):
            assert guard.apply_amendment({"new": 2}, "SIG_VALID") is True
            assert guard.constitution["new"] == 2

    def test_update_safety_axiom(self):
        # 1. Invalid magic bytes
        assert UpdateSafetyAxiom.verify_update(b"no_magic") is False

        # 2. Size constraint (> 5MB)
        assert (
            UpdateSafetyAxiom.verify_update(b"\x7fWL_PATCH" + b"a" * (6 * 1024 * 1024))
            is False
        )

        # 3. Missing PQC signature marker
        assert UpdateSafetyAxiom.verify_update(b"\x7fWL_PATCH_no_sig") is False

        # 4. Success - valid magic bytes, under 5MB, has PQC signature marker
        valid_patch = b"\x7fWL_PATCH---PQC_SIG_BEGIN---data---PQC_SIG_END---"
        assert UpdateSafetyAxiom.verify_update(valid_patch) is True

    def test_constitutional_audit_wrapper(self):
        with patch("warm_logic.kernel.constitution.guard") as mock_guard:
            mock_guard.sanitize.return_value = ("safe", 0)
            assert constitutional_audit("test") == ("safe", 0)
