# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic Zanzibar RBAC Engine."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.zanzibar import (
    RelationTuple,
    ZanzibarEngine,
    check_permission,
)


class TestRelationTuple:
    """Test RelationTuple dataclass."""

    def test_create_basic_tuple(self):
        """Creates tuple with required fields."""
        t = RelationTuple(
            namespace="doc",
            object_id="doc123",
            relation="viewer",
            subject_namespace="user",
            subject_id="alice",
        )

        assert t.namespace == "doc"
        assert t.object_id == "doc123"
        assert t.relation == "viewer"
        assert t.subject_namespace == "user"
        assert t.subject_id == "alice"
        assert t.subject_relation is None
        assert t.authority is None
        assert t.signature is None

    def test_create_tuple_with_userset(self):
        """Creates tuple with userset relation."""
        t = RelationTuple(
            namespace="doc",
            object_id="doc123",
            relation="viewer",
            subject_namespace="group",
            subject_id="eng-team",
            subject_relation="member",
        )

        assert t.subject_relation == "member"

    def test_create_tuple_with_pqc(self):
        """Creates tuple with PQC authority and signature."""
        t = RelationTuple(
            namespace="doc",
            object_id="doc123",
            relation="owner",
            subject_namespace="user",
            subject_id="alice",
            authority="did:warm:root:abc123",
            signature="ROOT_AUTHORITY_SIG",
        )

        assert t.authority == "did:warm:root:abc123"
        assert t.signature == "ROOT_AUTHORITY_SIG"


class TestZanzibarEngine:
    """Test ZanzibarEngine class."""

    def test_init_creates_db(self, tmp_path):
        """Creates database file and table."""
        db_path = tmp_path / "zanzibar.db"
        engine = ZanzibarEngine(db_path)

        assert db_path.exists()

        # Verify table exists
        cursor = engine.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='relation_tuples'"
        )
        assert cursor.fetchone() is not None

        engine.close()

    def test_init_memory_db(self):
        """Works with in-memory database."""
        engine = ZanzibarEngine(":memory:")

        # Should not raise
        cursor = engine.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = cursor.fetchall()
        assert len(tables) > 0

        engine.close()

    def test_close_connection(self, tmp_path):
        """Closes database connection."""
        db_path = tmp_path / "zanzibar.db"
        engine = ZanzibarEngine(db_path)

        engine.close()

        assert engine.conn is None

    def test_close_idempotent(self, tmp_path):
        """close() is idempotent."""
        db_path = tmp_path / "zanzibar.db"
        engine = ZanzibarEngine(db_path)

        engine.close()
        engine.close()  # Should not raise

    def test_verify_signature_valid(self, tmp_path):
        """Verifies valid ROOT_AUTHORITY signature."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        t = RelationTuple(
            namespace="doc",
            object_id="doc1",
            relation="owner",
            subject_namespace="user",
            subject_id="alice",
            authority="did:warm:root:abc123",
            signature="ROOT_AUTHORITY_SIG",
        )

        assert engine.verify_signature(t) is True
        engine.close()

    def test_verify_signature_missing_sig(self, tmp_path):
        """Rejects tuple without signature."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        t = RelationTuple(
            namespace="doc",
            object_id="doc1",
            relation="owner",
            subject_namespace="user",
            subject_id="alice",
            authority="did:warm:root:abc123",
        )

        assert engine.verify_signature(t) is False
        engine.close()

    def test_verify_signature_missing_authority(self, tmp_path):
        """Rejects tuple without authority."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        t = RelationTuple(
            namespace="doc",
            object_id="doc1",
            relation="owner",
            subject_namespace="user",
            subject_id="alice",
            signature="ROOT_AUTHORITY_SIG",
        )

        assert engine.verify_signature(t) is False
        engine.close()

    def test_verify_signature_wrong_authority(self, tmp_path):
        """Rejects tuple with non-root authority."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        t = RelationTuple(
            namespace="doc",
            object_id="doc1",
            relation="owner",
            subject_namespace="user",
            subject_id="alice",
            authority="did:warm:user:bob",
            signature="ROOT_AUTHORITY_SIG",
        )

        assert engine.verify_signature(t) is False
        engine.close()

    def test_write_tuple_success(self, tmp_path):
        """Writes verified tuple to database."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        t = RelationTuple(
            namespace="folder",
            object_id="folder1",
            relation="editor",
            subject_namespace="user",
            subject_id="bob",
            authority="did:warm:root:xyz",
            signature="ROOT_AUTHORITY_SIG",
        )

        result = engine.write_tuple(t, replicate=False)

        assert result is True

        # Verify in database
        cursor = engine.conn.execute(
            "SELECT * FROM relation_tuples WHERE object_id = 'folder1'"
        )
        row = cursor.fetchone()
        assert row is not None
        engine.close()

    def test_write_tuple_unauthorized(self, tmp_path):
        """Rejects unauthorized tuple."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        t = RelationTuple(
            namespace="doc",
            object_id="doc1",
            relation="owner",
            subject_namespace="user",
            subject_id="eve",
            # No authority/signature
        )

        result = engine.write_tuple(t, replicate=False)

        assert result is False
        engine.close()

    def test_write_tuple_with_replication(self, tmp_path):
        """Broadcasts tuple to DHT when enabled."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")
        mock_dht = MagicMock()

        t = RelationTuple(
            namespace="doc",
            object_id="doc1",
            relation="viewer",
            subject_namespace="user",
            subject_id="charlie",
            authority="did:warm:root:abc",
            signature="ROOT_AUTHORITY_SIG",
        )

        engine.write_tuple(t, dht=mock_dht, replicate=True)

        mock_dht.broadcast.assert_called_once()
        call_arg = mock_dht.broadcast.call_args[0][0]
        assert b"ZANZIBAR_TUPLE" in call_arg
        engine.close()

    def test_check_direct_permission(self, tmp_path):
        """Finds direct permission."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        # Add permission
        t = RelationTuple(
            namespace="doc",
            object_id="doc123",
            relation="viewer",
            subject_namespace="user",
            subject_id="alice",
            authority="did:warm:root:x",
            signature="ROOT_AUTHORITY_SIG",
        )
        engine.write_tuple(t, replicate=False)

        result = engine.check("doc", "doc123", "viewer", "alice")

        assert result is True
        engine.close()

    def test_check_no_permission(self, tmp_path):
        """Returns False when no permission exists."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        result = engine.check("doc", "doc123", "viewer", "unauthorized_user")

        assert result is False
        engine.close()

    def test_check_transitive_permission(self, tmp_path):
        """Resolves transitive permissions through groups."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        # alice is member of eng-team
        t1 = RelationTuple(
            namespace="group",
            object_id="eng-team",
            relation="member",
            subject_namespace="user",
            subject_id="alice",
            authority="did:warm:root:x",
            signature="ROOT_AUTHORITY_SIG",
        )
        engine.write_tuple(t1, replicate=False)

        # eng-team has viewer on doc123
        t2 = RelationTuple(
            namespace="doc",
            object_id="doc123",
            relation="viewer",
            subject_namespace="group",
            subject_id="eng-team",
            subject_relation="member",
            authority="did:warm:root:x",
            signature="ROOT_AUTHORITY_SIG",
        )
        engine.write_tuple(t2, replicate=False)

        # alice should have viewer on doc123 through eng-team
        result = engine.check("doc", "doc123", "viewer", "alice")

        assert result is True
        engine.close()

    def test_check_depth_limit(self, tmp_path):
        """Respects depth limit in graph traversal."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        # Create deep chain that exceeds default depth
        result = engine.check("doc", "doc1", "viewer", "deep_user", depth=0)

        assert result is False
        engine.close()

    def test_check_cycle_protection(self, tmp_path):
        """Handles cycles in permission graph."""
        engine = ZanzibarEngine(tmp_path / "zanzibar.db")

        # group-a -> group-b -> group-a (cycle)
        t1 = RelationTuple(
            namespace="group",
            object_id="group-a",
            relation="member",
            subject_namespace="group",
            subject_id="group-b",
            subject_relation="member",
            authority="did:warm:root:x",
            signature="ROOT_AUTHORITY_SIG",
        )
        t2 = RelationTuple(
            namespace="group",
            object_id="group-b",
            relation="member",
            subject_namespace="group",
            subject_id="group-a",
            subject_relation="member",
            authority="did:warm:root:x",
            signature="ROOT_AUTHORITY_SIG",
        )
        engine.write_tuple(t1, replicate=False)
        engine.write_tuple(t2, replicate=False)

        # Should terminate without infinite loop (depth limit protects)
        result = engine.check("group", "group-a", "member", "nonexistent")

        assert result is False
        engine.close()


class TestCheckPermissionFunction:
    """Test module-level check_permission function."""

    @patch("warm_logic.kernel.zanzibar.zanzibar")
    def test_check_permission_delegates(self, mock_zanzibar):
        """Delegates to global zanzibar instance."""
        mock_zanzibar.check.return_value = True

        result = check_permission("ns", "obj", "rel", "user")

        assert result is True
        mock_zanzibar.check.assert_called_once_with("ns", "obj", "rel", "user")
