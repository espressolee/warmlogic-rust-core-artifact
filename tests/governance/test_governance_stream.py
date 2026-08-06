"""Tests for Governance Stream."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from warm_logic_core.governance.governance_stream import (
    GovernanceStream,
    GovernanceStreamRecord,
    get_default_stream,
    record_governance_sample,
    append_govvm_decision,
)


class TestGovernanceStreamRecord:
    """Tests for GovernanceStreamRecord."""

    def test_record_creation(self):
        """Test record creation."""
        record = GovernanceStreamRecord.create(
            record_type="decision",
            data={"govSAT": "SatAllow"},
        )

        assert record.record_id.startswith("REC-")
        assert record.record_type == "decision"
        assert record.data["govSAT"] == "SatAllow"

    def test_record_to_dict(self):
        """Test record serialization."""
        record = GovernanceStreamRecord.create(
            record_type="sample",
            data={"metric": 100},
        )

        data = record.to_dict()

        assert data["schema_version"] == "governance_stream_record_v1"
        assert data["record_type"] == "sample"
        assert data["data"]["metric"] == 100

    def test_record_from_dict(self):
        """Test record deserialization."""
        data = {
            "record_id": "REC-TEST001",
            "timestamp": "2024-01-01T00:00:00Z",
            "record_type": "event",
            "data": {"event_type": "test"},
            "metadata": {"source": "test"},
        }

        record = GovernanceStreamRecord.from_dict(data)

        assert record.record_id == "REC-TEST001"
        assert record.record_type == "event"
        assert record.metadata["source"] == "test"


class TestGovernanceStream:
    """Tests for GovernanceStream."""

    def test_stream_initialization(self):
        """Test stream initialization."""
        stream = GovernanceStream()

        assert stream.stream_id.startswith("STREAM-")
        assert stream.buffer_size == 1000

    def test_stream_with_custom_id(self):
        """Test stream with custom ID."""
        stream = GovernanceStream(stream_id="STREAM-CUSTOM")

        assert stream.stream_id == "STREAM-CUSTOM"

    def test_append_record(self):
        """Test appending record."""
        stream = GovernanceStream()
        record = GovernanceStreamRecord.create("decision", {"test": True})

        stream.append(record)

        assert len(stream.get_recent(100)) == 1

    def test_buffer_limit(self):
        """Test buffer limit is enforced."""
        stream = GovernanceStream(buffer_size=10)

        for i in range(20):
            record = GovernanceStreamRecord.create("decision", {"index": i})
            stream.append(record)

        recent = stream.get_recent(100)

        assert len(recent) == 10
        # Should have most recent records
        assert recent[0].data["index"] == 10

    def test_get_recent(self):
        """Test getting recent records."""
        stream = GovernanceStream()

        for i in range(10):
            record = GovernanceStreamRecord.create("decision", {"index": i})
            stream.append(record)

        recent = stream.get_recent(5)

        assert len(recent) == 5
        assert recent[-1].data["index"] == 9

    def test_persistence(self):
        """Test file persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stream.jsonl"
            stream = GovernanceStream(persistence_path=path)

            for i in range(5):
                record = GovernanceStreamRecord.create("decision", {"index": i})
                stream.append(record)

            assert path.exists()

            with open(path) as f:
                lines = f.readlines()

            assert len(lines) == 5

    def test_replay(self):
        """Test replaying from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stream.jsonl"
            stream = GovernanceStream(persistence_path=path)

            for i in range(5):
                record = GovernanceStreamRecord.create("decision", {"index": i})
                stream.append(record)

            # Clear buffer and replay
            stream.clear()
            records = list(stream.replay())

            assert len(records) == 5
            assert records[0].data["index"] == 0

    def test_subscribe(self):
        """Test subscribing to stream."""
        stream = GovernanceStream()
        received = []

        def callback(record):
            received.append(record)

        stream.subscribe(callback)

        record = GovernanceStreamRecord.create("decision", {"test": True})
        stream.append(record)

        assert len(received) == 1
        assert received[0].data["test"] is True

    def test_unsubscribe(self):
        """Test unsubscribing from stream."""
        stream = GovernanceStream()
        received = []

        def callback(record):
            received.append(record)

        stream.subscribe(callback)
        result = stream.unsubscribe(callback)

        assert result is True

        record = GovernanceStreamRecord.create("decision", {"test": True})
        stream.append(record)

        assert len(received) == 0

    def test_unsubscribe_nonexistent(self):
        """Test unsubscribing nonexistent callback."""
        stream = GovernanceStream()

        def callback(record):
            pass

        result = stream.unsubscribe(callback)

        assert result is False

    def test_subscriber_error_ignored(self):
        """Test subscriber errors are ignored."""
        stream = GovernanceStream()

        def bad_callback(record):
            raise ValueError("Error")

        stream.subscribe(bad_callback)

        # Should not raise
        record = GovernanceStreamRecord.create("decision", {"test": True})
        stream.append(record)

    def test_clear(self):
        """Test clearing buffer."""
        stream = GovernanceStream()

        for i in range(10):
            record = GovernanceStreamRecord.create("decision", {"index": i})
            stream.append(record)

        stream.clear()

        assert len(stream.get_recent(100)) == 0

    def test_get_stats(self):
        """Test getting stream statistics."""
        stream = GovernanceStream()

        for i in range(5):
            record = GovernanceStreamRecord.create(
                "decision" if i % 2 == 0 else "sample",
                {"index": i},
            )
            stream.append(record)

        stats = stream.get_stats()

        assert stats["buffer_size"] == 5
        assert stats["record_types"]["decision"] == 3
        assert stats["record_types"]["sample"] == 2


class TestDefaultStream:
    """Tests for default stream functions."""

    def test_get_default_stream(self):
        """Test getting default stream."""
        stream1 = get_default_stream()
        stream2 = get_default_stream()

        assert stream1 is stream2

    def test_record_governance_sample(self):
        """Test recording governance sample."""
        record = record_governance_sample({"metric": 100})

        assert record.record_type == "sample"
        assert record.data["metric"] == 100

    def test_append_govvm_decision(self):
        """Test appending governance VM decision."""
        record = append_govvm_decision(
            {
                "govSAT": "SatAllow",
                "reason": "ok",
            }
        )

        assert record.record_type == "decision"
        assert record.data["govSAT"] == "SatAllow"

    def test_custom_stream(self):
        """Test using custom stream."""
        stream = GovernanceStream(stream_id="CUSTOM")

        record = record_governance_sample({"test": True}, stream=stream)

        assert len(stream.get_recent(10)) == 1
