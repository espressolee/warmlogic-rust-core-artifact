"""Tests for Decision Mapping."""

from __future__ import annotations

import pytest

from warm_logic_core.governance.decision_mapping import (
    DecisionMapping,
    PolicyResolution,
    PolicyResolver,
    get_default_resolver,
    resolve_policy,
    register_mapping,
)


class TestDecisionMapping:
    """Tests for DecisionMapping."""

    def test_mapping_creation(self):
        """Test mapping creation."""
        mapping = DecisionMapping.create(
            name="test_mapping",
            conditions=[{"field": "risk", "operator": "gt", "value": 0.5}],
            priority=50,
        )

        assert mapping.mapping_id.startswith("MAP-")
        assert mapping.name == "test_mapping"
        assert mapping.priority == 50

    def test_mapping_matches_eq(self):
        """Test mapping matches with eq operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "status", "operator": "eq", "value": "active"}],
        )

        assert mapping.matches({"status": "active"}) is True
        assert mapping.matches({"status": "inactive"}) is False

    def test_mapping_matches_neq(self):
        """Test mapping matches with neq operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "status", "operator": "neq", "value": "blocked"}],
        )

        assert mapping.matches({"status": "active"}) is True
        assert mapping.matches({"status": "blocked"}) is False

    def test_mapping_matches_gt(self):
        """Test mapping matches with gt operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "score", "operator": "gt", "value": 50}],
        )

        assert mapping.matches({"score": 75}) is True
        assert mapping.matches({"score": 50}) is False
        assert mapping.matches({"score": 25}) is False

    def test_mapping_matches_gte(self):
        """Test mapping matches with gte operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "score", "operator": "gte", "value": 50}],
        )

        assert mapping.matches({"score": 75}) is True
        assert mapping.matches({"score": 50}) is True
        assert mapping.matches({"score": 25}) is False

    def test_mapping_matches_lt(self):
        """Test mapping matches with lt operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "risk", "operator": "lt", "value": 0.3}],
        )

        assert mapping.matches({"risk": 0.1}) is True
        assert mapping.matches({"risk": 0.5}) is False

    def test_mapping_matches_lte(self):
        """Test mapping matches with lte operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "risk", "operator": "lte", "value": 0.3}],
        )

        assert mapping.matches({"risk": 0.3}) is True
        assert mapping.matches({"risk": 0.5}) is False

    def test_mapping_matches_in(self):
        """Test mapping matches with in operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "type", "operator": "in", "value": ["a", "b", "c"]}],
        )

        assert mapping.matches({"type": "a"}) is True
        assert mapping.matches({"type": "d"}) is False

    def test_mapping_matches_not_in(self):
        """Test mapping matches with not_in operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "type", "operator": "not_in", "value": ["x", "y"]}],
        )

        assert mapping.matches({"type": "a"}) is True
        assert mapping.matches({"type": "x"}) is False

    def test_mapping_matches_exists(self):
        """Test mapping matches with exists operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "token", "operator": "exists", "value": None}],
        )

        assert mapping.matches({"token": "abc"}) is True
        assert mapping.matches({"other": "value"}) is False

    def test_mapping_matches_not_exists(self):
        """Test mapping matches with not_exists operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "token", "operator": "not_exists", "value": None}],
        )

        assert mapping.matches({"other": "value"}) is True
        assert mapping.matches({"token": "abc"}) is False

    def test_mapping_matches_contains(self):
        """Test mapping matches with contains operator."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[
                {"field": "tags", "operator": "contains", "value": "important"}
            ],
        )

        assert mapping.matches({"tags": ["important", "urgent"]}) is True
        assert mapping.matches({"tags": ["normal"]}) is False

    def test_mapping_matches_multiple_conditions(self):
        """Test mapping matches with multiple conditions."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[
                {"field": "risk", "operator": "lt", "value": 0.5},
                {"field": "status", "operator": "eq", "value": "active"},
            ],
        )

        assert mapping.matches({"risk": 0.3, "status": "active"}) is True
        assert mapping.matches({"risk": 0.3, "status": "inactive"}) is False
        assert mapping.matches({"risk": 0.7, "status": "active"}) is False

    def test_mapping_disabled(self):
        """Test disabled mapping doesn't match."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "status", "operator": "eq", "value": "active"}],
        )
        mapping.enabled = False

        assert mapping.matches({"status": "active"}) is False

    def test_mapping_to_dict(self):
        """Test mapping serialization."""
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "x", "operator": "eq", "value": 1}],
        )

        data = mapping.to_dict()

        assert data["schema_version"] == "decision_mapping_v1"
        assert data["name"] == "test"


class TestPolicyResolution:
    """Tests for PolicyResolution."""

    def test_resolution_to_dict(self):
        """Test resolution serialization."""
        resolution = PolicyResolution(
            resolved=True,
            govSAT="SatAllow",
            govAction="continue",
            reason="matched",
        )

        data = resolution.to_dict()

        assert data["resolved"] is True
        assert data["govSAT"] == "SatAllow"


class TestPolicyResolver:
    """Tests for PolicyResolver."""

    def test_resolver_initialization(self):
        """Test resolver initialization."""
        resolver = PolicyResolver()

        assert len(resolver.get_mappings()) == 0

    def test_add_mapping(self):
        """Test adding mapping."""
        resolver = PolicyResolver()
        mapping = DecisionMapping.create("test", [])

        resolver.add_mapping(mapping)

        assert len(resolver.get_mappings()) == 1

    def test_remove_mapping(self):
        """Test removing mapping."""
        resolver = PolicyResolver()
        mapping = DecisionMapping.create("test", [])
        resolver.add_mapping(mapping)

        result = resolver.remove_mapping(mapping.mapping_id)

        assert result is True
        assert len(resolver.get_mappings()) == 0

    def test_remove_nonexistent_mapping(self):
        """Test removing nonexistent mapping."""
        resolver = PolicyResolver()

        result = resolver.remove_mapping("NONEXISTENT")

        assert result is False

    def test_resolve_no_mappings(self):
        """Test resolve with no mappings."""
        resolver = PolicyResolver()

        resolution = resolver.resolve({"test": True})

        assert resolution.resolved is False
        assert resolution.reason == "no_mapping_matched"

    def test_resolve_with_match(self):
        """Test resolve with matching mapping."""
        resolver = PolicyResolver()
        mapping = DecisionMapping.create(
            name="allow_active",
            conditions=[
                {
                    "field": "status",
                    "operator": "eq",
                    "value": "active",
                    "result_sat": "SatAllow",
                },
            ],
        )
        resolver.add_mapping(mapping)

        resolution = resolver.resolve({"status": "active"})

        assert resolution.resolved is True
        assert resolution.mapping.name == "allow_active"

    def test_resolve_priority_order(self):
        """Test resolve respects priority order."""
        resolver = PolicyResolver()

        low_priority = DecisionMapping.create(
            name="low",
            conditions=[{"field": "x", "operator": "eq", "value": 1}],
            priority=100,
        )
        high_priority = DecisionMapping.create(
            name="high",
            conditions=[{"field": "x", "operator": "eq", "value": 1}],
            priority=10,
        )

        resolver.add_mapping(low_priority)
        resolver.add_mapping(high_priority)

        resolution = resolver.resolve({"x": 1})

        assert resolution.mapping.name == "high"

    def test_resolve_trace(self):
        """Test resolve generates trace."""
        resolver = PolicyResolver()
        mapping = DecisionMapping.create(
            name="test",
            conditions=[{"field": "x", "operator": "eq", "value": 1}],
        )
        resolver.add_mapping(mapping)

        resolution = resolver.resolve({"x": 1})

        assert len(resolution.trace) > 0
        assert any("checking:test" in t for t in resolution.trace)
        assert any("matched:test" in t for t in resolution.trace)


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_default_resolver(self):
        """Test getting default resolver."""
        resolver1 = get_default_resolver()
        resolver2 = get_default_resolver()

        assert resolver1 is resolver2

    def test_resolve_policy(self):
        """Test resolve_policy function."""
        resolution = resolve_policy({"test": True})

        # Default resolver has no mappings
        assert resolution.resolved is False

    def test_register_mapping(self):
        """Test register_mapping function."""
        resolver = PolicyResolver()

        mapping = register_mapping(
            name="test_mapping",
            conditions=[{"field": "x", "operator": "eq", "value": 1}],
            priority=50,
            resolver=resolver,
        )

        assert mapping.name == "test_mapping"
        assert len(resolver.get_mappings()) == 1
