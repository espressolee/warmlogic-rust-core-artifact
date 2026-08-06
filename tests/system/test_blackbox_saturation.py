import json
import os
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from warm_logic.kernel.sys.blackbox import BlackBox


class TestBlackBoxSaturation:
    @pytest.fixture
    def tmp_ledger(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir) / "blackbox.jsonl"

    def test_init_creates_dir(self, tmp_ledger):
        """Test that initialization creates the necessary directory."""
        # tmp_ledger is already in a tmp_dir, but we'll try a nested one
        nested_ledger = tmp_ledger.parent / "subdir" / "audit.jsonl"
        BlackBox(str(nested_ledger))
        assert os.path.exists(nested_ledger.parent)

    def test_recover_state_missing_file(self, tmp_ledger):
        """Test recovery when file is missing."""
        bb = BlackBox(str(tmp_ledger))
        assert bb.index == 0
        assert bb.last_hash == "0" * 64

    def test_recover_state_success(self, tmp_ledger):
        """Test recovery from an existing ledger."""
        bb1 = BlackBox(str(tmp_ledger))
        bb1.log({"msg": "first"})
        bb1.log({"msg": "second"})
        last_hash = bb1.last_hash

        # New instance should recover
        bb2 = BlackBox(str(tmp_ledger))
        assert bb2.index == 2
        assert bb2.last_hash == last_hash

    def test_recover_state_empty_lines(self, tmp_ledger):
        """Test recovery skips empty lines."""
        with open(tmp_ledger, "w") as f:
            f.write(json.dumps({"index": 0, "hash": "h0", "content": {}}) + "\n")
            f.write("\n\n")
            f.write(json.dumps({"index": 1, "hash": "h1", "content": {}}) + "\n")
            f.write("   \n")

        bb = BlackBox(str(tmp_ledger))
        assert bb.index == 2
        assert bb.last_hash == "h1"

    def test_recover_state_exception(self, tmp_ledger):
        """Test error handling during recovery."""
        with open(tmp_ledger, "w") as f:
            f.write("{ invalid json }\n")

        # Should not raise, just log error
        bb = BlackBox(str(tmp_ledger))
        assert bb.index == 0  # Defaults

    def test_verify_integrity_missing_file(self, tmp_ledger):
        """Test integrity check when file is missing."""
        bb = BlackBox(str(tmp_ledger))
        assert bb.verify_integrity() is True

    def test_verify_integrity_success(self, tmp_ledger):
        """Test integrity check on a valid chain."""
        bb = BlackBox(str(tmp_ledger))
        bb.log({"a": 1})
        bb.log({"b": 2})
        assert bb.verify_integrity() is True

    def test_verify_integrity_prev_hash_mismatch(self, tmp_ledger):
        """Test detection of broken links (prev_hash mismatch)."""
        bb = BlackBox(str(tmp_ledger))
        bb.log({"a": 1})
        bb.log({"b": 2})

        # Tamper with prev_hash of second entry
        with open(tmp_ledger, "r") as f:
            lines = f.readlines()

        entry = json.loads(lines[1])
        entry["prev_hash"] = "tampered"
        lines[1] = json.dumps(entry) + "\n"

        with open(tmp_ledger, "w") as f:
            f.writelines(lines)

        assert bb.verify_integrity() is False

    def test_verify_integrity_hash_mismatch(self, tmp_ledger):
        """Test detection of content tampering (hash mismatch)."""
        bb = BlackBox(str(tmp_ledger))
        bb.log({"secret": "data"})

        # Tamper with content
        with open(tmp_ledger, "r") as f:
            lines = f.readlines()

        entry = json.loads(lines[0])
        entry["content"]["secret"] = "hacked"
        lines[0] = json.dumps(entry) + "\n"

        with open(tmp_ledger, "w") as f:
            f.writelines(lines)

        assert bb.verify_integrity() is False

    def test_verify_integrity_exception(self, tmp_ledger):
        """Test error handling during integrity audit."""
        bb = BlackBox(str(tmp_ledger))
        bb.log({"a": 1})

        # Mocking open to throw during verify_integrity
        with patch("builtins.open", side_effect=PermissionError("Locked")):
            assert bb.verify_integrity() is False

    def test_verify_integrity_skip_empty_lines(self, tmp_ledger):
        """Test integrity check skips empty lines."""
        bb = BlackBox(str(tmp_ledger))
        bb.log({"a": 1})
        with open(tmp_ledger, "a") as f:
            f.write("\n\n")
        bb.log({"b": 2})

        assert bb.verify_integrity() is True
