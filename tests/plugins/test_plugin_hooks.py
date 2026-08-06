# ==========================================================
# Tests: plugin_hooks.py
# ==========================================================
"""Tests for plugin hook system."""

import pytest
from unittest.mock import MagicMock

from warm_logic_core.plugins.plugin_hooks import (
    HookRegistry,
    HookType,
    HookPriority,
    Hook,
    HookResult,
    get_hook_registry,
    register_hook,
    invoke_hooks,
)


class TestHookType:
    """Tests for HookType enum."""

    def test_lifecycle_hooks(self):
        """Test lifecycle hook types."""
        assert HookType.BEFORE_LOAD.value == "before_load"
        assert HookType.AFTER_LOAD.value == "after_load"
        assert HookType.BEFORE_UNLOAD.value == "before_unload"
        assert HookType.AFTER_UNLOAD.value == "after_unload"

    def test_kernel_hooks(self):
        """Test kernel hook types."""
        assert HookType.KERNEL_TICK.value == "kernel_tick"
        assert HookType.KERNEL_STATE_CHANGE.value == "kernel_state_change"

    def test_governance_hooks(self):
        """Test governance hook types."""
        assert HookType.BEFORE_DECISION.value == "before_decision"
        assert HookType.AFTER_DECISION.value == "after_decision"

    def test_custom_hook(self):
        """Test custom hook type."""
        assert HookType.CUSTOM.value == "custom"


class TestHookPriority:
    """Tests for HookPriority enum."""

    def test_priority_ordering(self):
        """Test priority values are ordered correctly."""
        assert HookPriority.HIGHEST.value < HookPriority.HIGH.value
        assert HookPriority.HIGH.value < HookPriority.NORMAL.value
        assert HookPriority.NORMAL.value < HookPriority.LOW.value
        assert HookPriority.LOW.value < HookPriority.LOWEST.value


class TestHook:
    """Tests for Hook dataclass."""

    def test_create_hook(self):
        """Test hook creation."""
        handler = MagicMock()
        hook = Hook.create(
            hook_type=HookType.KERNEL_TICK,
            name="test-hook",
            handler=handler,
            priority=HookPriority.HIGH,
            plugin_id="PLUGIN-123",
        )

        assert hook.hook_id.startswith("HOOK-")
        assert hook.hook_type == HookType.KERNEL_TICK
        assert hook.name == "test-hook"
        assert hook.priority == HookPriority.HIGH
        assert hook.plugin_id == "PLUGIN-123"
        assert hook.enabled is True

    def test_to_dict(self):
        """Test hook serialization."""
        handler = MagicMock()
        hook = Hook.create(
            hook_type=HookType.BEFORE_DECISION,
            name="serialize-test",
            handler=handler,
        )

        data = hook.to_dict()
        assert "hook_id" in data
        assert data["hook_type"] == "before_decision"
        assert data["name"] == "serialize-test"
        assert data["enabled"] is True
        # Handler should not be in dict
        assert "handler" not in data


class TestHookResult:
    """Tests for HookResult dataclass."""

    def test_success_result(self):
        """Test success result."""
        result = HookResult(
            hook_id="HOOK-123",
            success=True,
            result="value",
            execution_time_ms=5.0,
        )
        assert result.success is True
        assert result.result == "value"
        assert result.error is None

    def test_failure_result(self):
        """Test failure result."""
        result = HookResult(
            hook_id="HOOK-123",
            success=False,
            error="Something failed",
        )
        assert result.success is False
        assert result.error == "Something failed"

    def test_to_dict(self):
        """Test result serialization."""
        result = HookResult(
            hook_id="HOOK-123",
            success=True,
            execution_time_ms=10.0,
        )
        data = result.to_dict()
        assert data["hook_id"] == "HOOK-123"
        assert data["success"] is True
        assert data["execution_time_ms"] == 10.0


class TestHookRegistry:
    """Tests for HookRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create test registry."""
        return HookRegistry(enable_circuit_breaker=False)

    def test_register_hook(self, registry):
        """Test hook registration."""
        handler = MagicMock()
        hook = Hook.create(HookType.KERNEL_TICK, "test", handler)

        hook_id = registry.register(hook)
        assert hook_id == hook.hook_id

        hooks = registry.get_hooks(HookType.KERNEL_TICK)
        assert len(hooks) == 1
        assert hooks[0].name == "test"

    def test_unregister_hook(self, registry):
        """Test hook unregistration."""
        handler = MagicMock()
        hook = Hook.create(HookType.KERNEL_TICK, "test", handler)
        hook_id = registry.register(hook)

        result = registry.unregister(hook_id)
        assert result is True
        assert len(registry.get_hooks(HookType.KERNEL_TICK)) == 0

    def test_unregister_nonexistent(self, registry):
        """Test unregistering nonexistent hook."""
        result = registry.unregister("HOOK-NONEXISTENT")
        assert result is False

    def test_unregister_by_plugin(self, registry):
        """Test unregistering by plugin ID."""
        handler = MagicMock()
        hook1 = Hook.create(HookType.KERNEL_TICK, "h1", handler, plugin_id="P1")
        hook2 = Hook.create(HookType.AFTER_LOAD, "h2", handler, plugin_id="P1")
        hook3 = Hook.create(HookType.BEFORE_DECISION, "h3", handler, plugin_id="P2")

        registry.register(hook1)
        registry.register(hook2)
        registry.register(hook3)

        count = registry.unregister_by_plugin("P1")
        assert count == 2

        # P2's hook should remain
        assert len(registry.get_hooks(HookType.BEFORE_DECISION)) == 1

    def test_invoke_hooks(self, registry):
        """Test invoking hooks."""
        handler1 = MagicMock(return_value="result1")
        handler2 = MagicMock(return_value="result2")

        hook1 = Hook.create(HookType.KERNEL_TICK, "h1", handler1)
        hook2 = Hook.create(HookType.KERNEL_TICK, "h2", handler2)

        registry.register(hook1)
        registry.register(hook2)

        results = registry.invoke(HookType.KERNEL_TICK, "arg1", kwarg="value")

        assert len(results) == 2
        handler1.assert_called_once_with("arg1", kwarg="value")
        handler2.assert_called_once_with("arg1", kwarg="value")

    def test_invoke_respects_priority(self, registry):
        """Test hooks are invoked in priority order."""
        call_order = []

        def handler1():
            call_order.append("low")
            return "low"

        def handler2():
            call_order.append("high")
            return "high"

        hook1 = Hook.create(
            HookType.KERNEL_TICK, "low", handler1, priority=HookPriority.LOW
        )
        hook2 = Hook.create(
            HookType.KERNEL_TICK, "high", handler2, priority=HookPriority.HIGH
        )

        # Register in reverse order
        registry.register(hook1)
        registry.register(hook2)

        registry.invoke(HookType.KERNEL_TICK)

        # High priority should be called first
        assert call_order == ["high", "low"]

    def test_invoke_disabled_hooks_skipped(self, registry):
        """Test disabled hooks are skipped."""
        handler = MagicMock()
        hook = Hook.create(HookType.KERNEL_TICK, "test", handler)
        hook.enabled = False

        registry.register(hook)
        results = registry.invoke(HookType.KERNEL_TICK)

        assert len(results) == 0
        handler.assert_not_called()

    def test_invoke_handles_exceptions(self, registry):
        """Test hook exceptions are handled."""

        def failing_handler():
            raise ValueError("Intentional error")

        hook = Hook.create(HookType.KERNEL_TICK, "fail", failing_handler)
        registry.register(hook)

        results = registry.invoke(HookType.KERNEL_TICK)

        assert len(results) == 1
        assert results[0].success is False
        assert "Intentional error" in results[0].error

    def test_invoke_stop_on_error(self, registry):
        """Test stop_on_error behavior."""
        handler1 = MagicMock(side_effect=ValueError("error"))
        handler2 = MagicMock()

        hook1 = Hook.create(
            HookType.KERNEL_TICK, "h1", handler1, priority=HookPriority.HIGH
        )
        hook2 = Hook.create(
            HookType.KERNEL_TICK, "h2", handler2, priority=HookPriority.LOW
        )

        registry.register(hook1)
        registry.register(hook2)

        results = registry.invoke(HookType.KERNEL_TICK, stop_on_error=True)

        assert len(results) == 1
        handler2.assert_not_called()

    def test_invoke_first(self, registry):
        """Test invoke_first returns first successful result."""

        def handler1():
            return None

        def handler2():
            return "result"

        hook1 = Hook.create(
            HookType.BEFORE_DECISION, "h1", handler1, priority=HookPriority.HIGH
        )
        hook2 = Hook.create(
            HookType.BEFORE_DECISION, "h2", handler2, priority=HookPriority.LOW
        )

        registry.register(hook1)
        registry.register(hook2)

        result = registry.invoke_first(HookType.BEFORE_DECISION)
        assert result == "result"

    def test_invoke_first_with_default(self, registry):
        """Test invoke_first with default."""
        result = registry.invoke_first(HookType.KERNEL_TICK, default="default")
        assert result == "default"

    def test_get_hook(self, registry):
        """Test getting hook by ID."""
        handler = MagicMock()
        hook = Hook.create(HookType.KERNEL_TICK, "test", handler)
        hook_id = registry.register(hook)

        found = registry.get_hook(hook_id)
        assert found is not None
        assert found.name == "test"

    def test_get_hook_nonexistent(self, registry):
        """Test getting nonexistent hook."""
        found = registry.get_hook("HOOK-NONEXISTENT")
        assert found is None

    def test_enable_disable_hook(self, registry):
        """Test enable/disable hook."""
        handler = MagicMock()
        hook = Hook.create(HookType.KERNEL_TICK, "test", handler)
        hook_id = registry.register(hook)

        assert registry.disable(hook_id) is True
        assert registry.get_hook(hook_id).enabled is False

        assert registry.enable(hook_id) is True
        assert registry.get_hook(hook_id).enabled is True

    def test_enable_disable_nonexistent(self, registry):
        """Test enable/disable nonexistent hook."""
        assert registry.enable("HOOK-NONE") is False
        assert registry.disable("HOOK-NONE") is False

    def test_get_stats(self, registry):
        """Test registry statistics."""
        handler = MagicMock(return_value=True)
        failing = MagicMock(side_effect=ValueError("error"))

        hook1 = Hook.create(HookType.KERNEL_TICK, "h1", handler)
        hook2 = Hook.create(HookType.AFTER_LOAD, "h2", failing)

        registry.register(hook1)
        registry.register(hook2)

        registry.invoke(HookType.KERNEL_TICK)
        registry.invoke(HookType.AFTER_LOAD)

        stats = registry.get_stats()
        assert stats["total_hooks"] == 2
        assert stats["invocation_count"] == 2
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1

    def test_reset(self, registry):
        """Test registry reset."""
        handler = MagicMock()
        hook = Hook.create(HookType.KERNEL_TICK, "test", handler)
        registry.register(hook)

        registry.reset()

        assert registry.get_hooks(HookType.KERNEL_TICK) == []
        stats = registry.get_stats()
        assert stats["total_hooks"] == 0
        assert stats["invocation_count"] == 0


class TestHookRegistryCircuitBreaker:
    """Tests for circuit breaker integration."""

    @pytest.fixture
    def registry(self):
        """Create registry with circuit breaker enabled."""
        return HookRegistry(enable_circuit_breaker=True)

    def test_circuit_breaker_created(self, registry):
        """Test circuit breaker is created on registration."""
        handler = MagicMock()
        hook = Hook.create(HookType.KERNEL_TICK, "test", handler)
        hook_id = registry.register(hook)

        assert hook_id in registry._circuit_breakers

    def test_circuit_breaker_opens_on_failures(self, registry):
        """Test circuit breaker opens after failures."""

        def failing():
            raise ValueError("error")

        hook = Hook.create(HookType.KERNEL_TICK, "fail", failing)
        registry.register(hook)

        # Trigger enough failures to open circuit
        for _ in range(5):
            registry.invoke(HookType.KERNEL_TICK)

        # Next invocation should show circuit open
        results = registry.invoke(HookType.KERNEL_TICK)
        assert len(results) == 1
        assert "Circuit breaker open" in results[0].error


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_hook_registry_returns_singleton(self):
        """Test global registry is singleton."""
        reg1 = get_hook_registry()
        reg2 = get_hook_registry()
        assert reg1 is reg2
        assert reg1.registry_id == "GLOBAL-HOOKS"

    def test_register_hook_function(self):
        """Test register_hook convenience function."""
        handler = MagicMock()
        hook_id = register_hook(
            HookType.CUSTOM,
            "test-global-hook",
            handler,
            priority=HookPriority.HIGH,
            plugin_id="TEST-PLUGIN",
        )

        assert hook_id.startswith("HOOK-")

        # Cleanup
        get_hook_registry().unregister(hook_id)

    def test_invoke_hooks_function(self):
        """Test invoke_hooks convenience function."""
        handler = MagicMock(return_value="result")
        hook_id = register_hook(HookType.CUSTOM, "test-invoke", handler)

        try:
            results = invoke_hooks(HookType.CUSTOM, "arg", key="value")
            handler.assert_called_with("arg", key="value")
        finally:
            get_hook_registry().unregister(hook_id)
