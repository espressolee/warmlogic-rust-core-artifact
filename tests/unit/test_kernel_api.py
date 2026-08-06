# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""
[P0xx] Unit tests for kernel API module.
Tests: api.py - Public interface for WarmLogic kernel operations
"""

import unittest
from unittest import mock

from warm_logic.kernel.api import (
    ModeDecision,
    ModeDecisionContext,
    ModeRule,
    ModuleRegistry,
    _normalize_ct_action,
    _normalize_gov_action,
    trigger_intelligence_tick,
)


class TestModeDecisionContext(unittest.TestCase):
    """Test ModeDecisionContext dataclass."""

    def test_create_context(self):
        """Test creating a decision context."""
        ctx = ModeDecisionContext(
            active_mode="NORMAL",
            metrics={"cpu": 0.5, "memory": 0.3},
        )
        self.assertEqual(ctx.active_mode, "NORMAL")
        self.assertEqual(ctx.metrics["cpu"], 0.5)

    def test_context_is_frozen(self):
        """Test context is immutable."""
        ctx = ModeDecisionContext(active_mode="SAFE", metrics={})
        with self.assertRaises(AttributeError):
            ctx.active_mode = "PANIC"


class TestModeDecision(unittest.TestCase):
    """Test ModeDecision dataclass."""

    def test_create_decision(self):
        """Test creating a mode decision."""
        decision = ModeDecision(mode="SAFE", reason="High entropy detected")
        self.assertEqual(decision.mode, "SAFE")
        self.assertEqual(decision.reason, "High entropy detected")

    def test_decision_is_frozen(self):
        """Test decision is immutable."""
        decision = ModeDecision(mode="NORMAL", reason="OK")
        with self.assertRaises(AttributeError):
            decision.mode = "PANIC"


class TestModeRule(unittest.TestCase):
    """Test ModeRule dataclass."""

    def test_create_rule(self):
        """Test creating a mode rule."""
        rule = ModeRule(trigger="entropy > 0.8", target_mode="SAFE")
        self.assertEqual(rule.trigger, "entropy > 0.8")
        self.assertEqual(rule.target_mode, "SAFE")


class TestModuleRegistry(unittest.TestCase):
    """Test ModuleRegistry for plugin architecture."""

    def setUp(self):
        """Clear registry before each test."""
        ModuleRegistry._handlers = {}

    def test_register_module(self):
        """Test registering a module."""
        handler = lambda x: x * 2
        ModuleRegistry.register("test.module", handler)
        self.assertTrue(ModuleRegistry.has_module("test.module"))

    def test_get_registered_module(self):
        """Test getting a registered module."""
        handler = lambda x: x + 1
        ModuleRegistry.register("math.add", handler)
        retrieved = ModuleRegistry.get("math.add")
        self.assertEqual(retrieved(5), 6)

    def test_get_unregistered_module(self):
        """Test getting unregistered module returns None."""
        result = ModuleRegistry.get("nonexistent")
        self.assertIsNone(result)

    def test_has_module_false(self):
        """Test has_module returns False for unregistered."""
        self.assertFalse(ModuleRegistry.has_module("missing"))

    def test_register_overwrites(self):
        """Test registering same name overwrites."""
        ModuleRegistry.register("dup", lambda: 1)
        ModuleRegistry.register("dup", lambda: 2)
        self.assertEqual(ModuleRegistry.get("dup")(), 2)


class TestNormalizeFunctions(unittest.TestCase):
    """Test normalization helper functions."""

    def test_normalize_gov_action_with_value(self):
        """Test normalizing governance action with value."""
        result = _normalize_gov_action("APPROVE")
        self.assertEqual(result, "APPROVE")

    def test_normalize_gov_action_none(self):
        """Test normalizing governance action with None."""
        result = _normalize_gov_action(None)
        self.assertIsNone(result)

    def test_normalize_gov_action_empty(self):
        """Test normalizing governance action with empty string."""
        result = _normalize_gov_action("")
        self.assertIsNone(result)

    def test_normalize_ct_action(self):
        """Test normalizing CT action."""
        result = _normalize_ct_action(123)
        self.assertEqual(result, "123")

    def test_normalize_ct_action_string(self):
        """Test normalizing CT action with string."""
        result = _normalize_ct_action("action")
        self.assertEqual(result, "action")


class TestTriggerIntelligenceTick(unittest.TestCase):
    """Test intelligence tick trigger."""

    def setUp(self):
        """Clear registry before each test."""
        ModuleRegistry._handlers = {}

    def test_trigger_without_handler(self):
        """Test trigger returns None without handler."""
        result = trigger_intelligence_tick({"test": 1})
        self.assertIsNone(result)

    def test_trigger_with_handler(self):
        """Test trigger calls registered handler."""
        handler = mock.MagicMock(return_value="processed")
        ModuleRegistry.register("dominion.intelligence", handler)

        result = trigger_intelligence_tick({"cpu": 0.5})

        handler.assert_called_once_with({"cpu": 0.5})
        self.assertEqual(result, "processed")


class TestComputeMode(unittest.TestCase):
    """Test compute_mode function."""

    @mock.patch("warm_logic.kernel.api.rust_loader.HAS_RUST_CORE", False)
    def test_compute_mode_without_rust(self):
        """Test compute_mode raises without Rust core."""
        from warm_logic.kernel.api import compute_mode

        ctx = ModeDecisionContext(active_mode="NORMAL", metrics={})
        with self.assertRaises(RuntimeError) as exc:
            compute_mode(ctx)
        self.assertIn("Rust Core missing", str(exc.exception))

    @mock.patch("warm_logic.kernel.api.rust_loader.HAS_RUST_CORE", True)
    @mock.patch("warm_logic.kernel.api.rust_loader.load_rust_core")
    @mock.patch("warm_logic.kernel.api._RUST_LOOP", None)
    def test_compute_mode_with_rust(self, mock_load):
        """Test compute_mode with Rust core."""
        from warm_logic.kernel.api import compute_mode

        # Reset global
        import warm_logic.kernel.api as api_module

        api_module._RUST_LOOP = None

        mock_rs = mock.MagicMock()
        mock_loop = mock.MagicMock()
        mock_result = mock.MagicMock()
        mock_result.mode = "SAFE"
        mock_result.reason = "Entropy high"
        mock_loop.compute_mode.return_value = mock_result
        mock_rs.ReflectiveLoop.return_value = mock_loop
        mock_load.return_value = mock_rs

        ctx = ModeDecisionContext(active_mode="NORMAL", metrics={"entropy": 0.9})
        result = compute_mode(ctx)

        self.assertEqual(result.mode, "SAFE")
        self.assertEqual(result.reason, "Entropy high")


if __name__ == "__main__":
    unittest.main()
