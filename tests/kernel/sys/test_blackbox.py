# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic BlackBox audit ledger."""

import hashlib
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from warm_logic.kernel.sys.blackbox import BlackBox


class TestBlackBox:
    """Test BlackBox append-only ledger."""

    def test_init_creates_directory(self, tmp_path):
        """Creates parent directory if it doesn't exist."""
        ledger_path = tmp_path / "audit" / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        assert (tmp_path / "audit").exists()
        assert box.last_hash == "0" * 64
        assert box.index == 0

    def test_log_creates_entry(self, tmp_path):
        """Logs entry with correct structure."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        box.log({"action": "test", "value": 123})

        assert ledger_path.exists()
        with open(ledger_path) as f:
            entry = json.loads(f.readline())

        assert entry["index"] == 0
        assert "timestamp" in entry
        assert entry["content"] == {"action": "test", "value": 123}
        assert entry["prev_hash"] == "0" * 64
        assert len(entry["hash"]) == 64

    def test_log_updates_chain_state(self, tmp_path):
        """Updates last_hash and index after logging."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        initial_hash = box.last_hash
        box.log({"test": 1})

        assert box.index == 1
        assert box.last_hash != initial_hash
        assert len(box.last_hash) == 64

    def test_log_multiple_entries_chain(self, tmp_path):
        """Multiple entries form a valid hash chain."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        box.log({"entry": 1})
        first_hash = box.last_hash
        box.log({"entry": 2})
        second_hash = box.last_hash

        # Read entries
        with open(ledger_path) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 2
        assert entries[0]["hash"] == first_hash
        assert entries[1]["prev_hash"] == first_hash
        assert entries[1]["hash"] == second_hash

    def test_verify_integrity_empty_ledger(self, tmp_path):
        """Empty ledger passes verification."""
        ledger_path = tmp_path / "nonexistent.jsonl"
        box = BlackBox(str(ledger_path))

        assert box.verify_integrity() is True

    def test_verify_integrity_valid_chain(self, tmp_path):
        """Valid chain passes verification."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        box.log({"a": 1})
        box.log({"b": 2})
        box.log({"c": 3})

        assert box.verify_integrity() is True

    def test_verify_integrity_detects_tampered_hash(self, tmp_path):
        """Detects tampered hash."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        box.log({"test": 1})

        # Tamper with the hash
        with open(ledger_path) as f:
            entry = json.loads(f.readline())
        entry["hash"] = "a" * 64
        with open(ledger_path, "w") as f:
            f.write(json.dumps(entry) + "\n")

        assert box.verify_integrity() is False

    def test_verify_integrity_detects_broken_chain(self, tmp_path):
        """Detects broken prev_hash chain."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        box.log({"entry": 1})
        box.log({"entry": 2})

        # Tamper with prev_hash of second entry
        with open(ledger_path) as f:
            entries = [json.loads(line) for line in f]
        entries[1]["prev_hash"] = "b" * 64
        with open(ledger_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        assert box.verify_integrity() is False

    def test_recover_state_from_existing_ledger(self, tmp_path):
        """Recovers chain state from existing ledger."""
        ledger_path = tmp_path / "blackbox.jsonl"

        # First instance creates entries
        box1 = BlackBox(str(ledger_path))
        box1.log({"first": True})
        box1.log({"second": True})
        last_hash = box1.last_hash
        last_index = box1.index

        # Second instance recovers state
        box2 = BlackBox(str(ledger_path))

        assert box2.last_hash == last_hash
        assert box2.index == last_index

    def test_recover_state_handles_empty_lines(self, tmp_path):
        """Recovery ignores empty lines in ledger."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box1 = BlackBox(str(ledger_path))
        box1.log({"test": 1})

        # Add empty lines
        with open(ledger_path, "a") as f:
            f.write("\n\n")

        box2 = BlackBox(str(ledger_path))
        assert box2.index == 1

    def test_hash_is_deterministic(self, tmp_path):
        """Same input produces same hash."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        content = {"key": "value", "nested": {"a": 1}}
        box.log(content)

        # Read the entry
        with open(ledger_path) as f:
            entry = json.loads(f.readline())

        # Manually recompute
        content_str = json.dumps(content, sort_keys=True)
        payload = f"{entry['index']}{entry['timestamp']}{entry['prev_hash']}{content_str}".encode()
        expected_hash = hashlib.sha256(payload).hexdigest()

        assert entry["hash"] == expected_hash

    def test_content_is_sorted_for_hashing(self, tmp_path):
        """Content keys are sorted for consistent hashing."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        # Order of keys shouldn't matter
        box.log({"z": 1, "a": 2, "m": 3})

        with open(ledger_path) as f:
            entry = json.loads(f.readline())

        # Verify sort_keys was applied
        content_str = json.dumps(entry["content"], sort_keys=True)
        assert content_str == '{"a": 2, "m": 3, "z": 1}'

    @patch("warm_logic.kernel.sys.blackbox.os.path.exists")
    def test_recover_handles_read_error(self, mock_exists, tmp_path, caplog):
        """Recovery logs error on file read failure."""
        ledger_path = tmp_path / "blackbox.jsonl"

        # Create a valid file first
        ledger_path.write_text('{"invalid json\n')
        mock_exists.return_value = True

        with patch("builtins.open", side_effect=Exception("Read error")):
            # Should not raise, just log error
            box = BlackBox(str(ledger_path))

        # State should remain at genesis
        assert box.last_hash == "0" * 64
        assert box.index == 0

    def test_verify_integrity_skips_empty_lines(self, tmp_path):
        """Verification skips empty lines in ledger."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        # Log an entry
        box.log({"test": 1})

        # Manually add empty lines to the file
        with open(ledger_path, "a") as f:
            f.write("\n\n")

        # Should still verify successfully
        assert box.verify_integrity() is True

    def test_verify_integrity_handles_json_error(self, tmp_path):
        """Verification returns False on JSON parse error."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))

        # Write invalid JSON
        ledger_path.write_text("not valid json\n")

        # Should return False due to exception
        assert box.verify_integrity() is False

    def test_verify_integrity_handles_file_read_error(self, tmp_path):
        """Verification returns False on file read error."""
        ledger_path = tmp_path / "blackbox.jsonl"
        box = BlackBox(str(ledger_path))
        box.log({"test": 1})

        # Mock file read to raise exception
        with patch("builtins.open", side_effect=IOError("Read error")):
            result = box.verify_integrity()

        assert result is False
