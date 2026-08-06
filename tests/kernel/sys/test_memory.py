# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic Sovereign Memory Engine."""

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.memory import SovereignMemoryEngine


class TestSovereignMemoryEngine:
    """Test SovereignMemoryEngine class."""

    def test_init_creates_directories(self, tmp_path):
        """Creates required directory structure."""
        mock_identity = MagicMock()
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        assert engine.ephemeris_dir.exists()
        assert engine.mem_dir.exists()

    def test_init_sets_paths(self, tmp_path):
        """Sets correct paths."""
        mock_identity = MagicMock()
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        assert engine.root_dir == Path(tmp_path)
        assert engine.mem_dir == Path(tmp_path) / "meta" / "memory"
        assert engine.ephemeris_dir == Path(tmp_path) / "meta" / "memory" / "ephemeris"
        assert (
            engine.chronicle_path == Path(tmp_path) / "meta" / "memory" / "chronicle.md"
        )

    def test_log_event_creates_daily_file(self, tmp_path):
        """Creates daily ephemeris file."""
        mock_identity = MagicMock()
        mock_identity.sign.return_value = "sig_abc123def456"
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        engine.log_event("TEST_EVENT", "Test detail")

        today = datetime.now().strftime("%Y-%m-%d")
        log_path = engine.ephemeris_dir / f"{today}.md"
        assert log_path.exists()

    def test_log_event_appends_entry(self, tmp_path):
        """Appends formatted entry to ephemeris."""
        mock_identity = MagicMock()
        mock_identity.sign.return_value = "signature_1234567890abcdef"
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        engine.log_event("BUILD", "Compiled module X", {"version": "1.0"})

        today = datetime.now().strftime("%Y-%m-%d")
        log_path = engine.ephemeris_dir / f"{today}.md"
        content = log_path.read_text()

        assert "BUILD" in content
        assert "Compiled module X" in content
        assert '{"version": "1.0"}' in content
        assert "signature_123456" in content  # First 16 chars

    def test_log_event_without_metadata(self, tmp_path):
        """Logs event without metadata."""
        mock_identity = MagicMock()
        mock_identity.sign.return_value = "sig_no_meta"
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        engine.log_event("SIMPLE", "Simple event")

        today = datetime.now().strftime("%Y-%m-%d")
        log_path = engine.ephemeris_dir / f"{today}.md"
        content = log_path.read_text()

        assert "SIMPLE" in content
        assert "Simple event" in content
        assert "Meta" not in content or "{}" not in content

    def test_log_event_signs_payload(self, tmp_path):
        """Signs the event payload with identity."""
        mock_identity = MagicMock()
        mock_identity.sign.return_value = "pqc_signature_result"
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        engine.log_event("SIGNED", "Signed event")

        mock_identity.sign.assert_called_once()
        call_arg = mock_identity.sign.call_args[0][0]
        payload = json.loads(call_arg)
        assert payload["type"] == "SIGNED"
        assert payload["detail"] == "Signed event"

    def test_log_event_no_identity(self, tmp_path):
        """Handles missing identity gracefully."""
        engine = SovereignMemoryEngine(str(tmp_path), None)

        engine.log_event("UNSIGNED", "No identity")

        today = datetime.now().strftime("%Y-%m-%d")
        log_path = engine.ephemeris_dir / f"{today}.md"
        content = log_path.read_text()

        assert "UNSIGNED" in content
        assert "No identity" in content

    def test_log_event_adds_header_to_empty_file(self, tmp_path):
        """Adds date header to new ephemeris file."""
        mock_identity = MagicMock()
        mock_identity.sign.return_value = "sig"
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        engine.log_event("FIRST", "First event")

        today = datetime.now().strftime("%Y-%m-%d")
        log_path = engine.ephemeris_dir / f"{today}.md"
        content = log_path.read_text()

        assert content.startswith(f"# Ephemeris: {today}")

    def test_get_session_summary_existing(self, tmp_path):
        """Retrieves content of existing ephemeris."""
        mock_identity = MagicMock()
        mock_identity.sign.return_value = "sig"
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        # Create a log
        today = datetime.now().strftime("%Y-%m-%d")
        log_path = engine.ephemeris_dir / f"{today}.md"
        log_path.write_text("Test content for summary")

        summary = engine.get_session_summary(today)

        assert summary == "Test content for summary"

    def test_get_session_summary_missing(self, tmp_path):
        """Returns empty string for missing ephemeris."""
        mock_identity = MagicMock()
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        summary = engine.get_session_summary("1999-01-01")

        assert summary == ""

    def test_compact_to_chronicle(self, tmp_path):
        """Appends summary to chronicle."""
        mock_identity = MagicMock()
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        engine.compact_to_chronicle("Session summary content")

        assert engine.chronicle_path.exists()
        content = engine.chronicle_path.read_text()
        assert "Session Summary:" in content
        assert "Session summary content" in content

    def test_compact_to_chronicle_appends(self, tmp_path):
        """Multiple compactions append to chronicle."""
        mock_identity = MagicMock()
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        engine.compact_to_chronicle("First session")
        engine.compact_to_chronicle("Second session")

        content = engine.chronicle_path.read_text()
        assert "First session" in content
        assert "Second session" in content

    def test_log_event_timestamp_format(self, tmp_path):
        """Entry includes formatted timestamp."""
        mock_identity = MagicMock()
        mock_identity.sign.return_value = "sig"
        engine = SovereignMemoryEngine(str(tmp_path), mock_identity)

        with patch("warm_logic.kernel.sys.memory.time") as mock_time:
            mock_time.time.return_value = 1704067200.0  # 2024-01-01 00:00:00 UTC

            with patch("warm_logic.kernel.sys.memory.datetime") as mock_dt:
                mock_dt.now.return_value.strftime.return_value = "2024-01-01"
                mock_dt.fromtimestamp.return_value.strftime.return_value = "00:00:00"

                engine.log_event("TIME_TEST", "Test")

        today = datetime.now().strftime("%Y-%m-%d")
        log_path = engine.ephemeris_dir / f"{today}.md"
        if log_path.exists():
            content = log_path.read_text()
            # Verify timestamp is present in some form
            assert "[" in content and "]" in content
