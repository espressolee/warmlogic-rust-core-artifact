# ==========================================================
# Tests: plugin_context.py
# ==========================================================
"""Tests for plugin context with OS integration."""

import pytest
from unittest.mock import MagicMock, patch

from warm_logic_core.plugins.plugin_context import (
    PluginContext,
    PluginInfo,
    PluginState,
    create_plugin_context,
)
from warm_logic_core.os.event_bus import EventPriority
from warm_logic_core.os.circuit_breaker import CircuitConfig
from warm_logic_core.os.schema_validator import (
    ObjectSchema,
    FieldSchema,
    FieldType,
)


class TestPluginInfo:
    """Tests for PluginInfo dataclass."""

    def test_create_generates_id(self):
        """Test that create generates a unique plugin ID."""
        info = PluginInfo.create("test-plugin", "1.0.0")
        assert info.plugin_id.startswith("PLUGIN-")
        assert info.name == "test-plugin"
        assert info.version == "1.0.0"

    def test_to_dict_serialization(self):
        """Test serialization to dictionary."""
        info = PluginInfo(
            plugin_id="PLUGIN-TEST",
            name="test",
            version="2.0.0",
            author="author",
            description="desc",
            dependencies=["dep1"],
            capabilities=["cap1"],
        )
        data = info.to_dict()
        assert data["plugin_id"] == "PLUGIN-TEST"
        assert data["name"] == "test"
        assert data["version"] == "2.0.0"
        assert data["author"] == "author"
        assert data["dependencies"] == ["dep1"]
        assert data["capabilities"] == ["cap1"]

    def test_defaults(self):
        """Test default values."""
        info = PluginInfo(plugin_id="P1", name="test")
        assert info.version == "1.0.0"
        assert info.author == "unknown"
        assert info.dependencies == []
        assert info.capabilities == []


class TestPluginState:
    """Tests for PluginState enum."""

    def test_all_states_exist(self):
        """Test all expected states exist."""
        assert PluginState.UNLOADED.value == "unloaded"
        assert PluginState.LOADING.value == "loading"
        assert PluginState.LOADED.value == "loaded"
        assert PluginState.ACTIVE.value == "active"
        assert PluginState.SUSPENDED.value == "suspended"
        assert PluginState.ERROR.value == "error"
        assert PluginState.UNLOADING.value == "unloading"


class TestPluginContext:
    """Tests for PluginContext class."""

    @pytest.fixture
    def plugin_info(self):
        """Create test plugin info."""
        return PluginInfo.create("test-plugin", "1.0.0")

    @pytest.fixture
    def context(self, plugin_info):
        """Create test plugin context."""
        return PluginContext(plugin_info)

    def test_initial_state(self, context):
        """Test initial context state."""
        assert context.state == PluginState.UNLOADED
        assert context.info.name == "test-plugin"

    def test_state_transition_emits_event(self, context):
        """Test state change emits event."""
        events_received = []

        def handler(event):
            events_received.append(event)

        context.subscribe(
            handler, event_types={f"plugin.{context.info.name}.state_changed"}
        )
        context.state = PluginState.LOADING

        assert context.state == PluginState.LOADING
        # Event should be queued

    def test_lifecycle_on_load(self, context):
        """Test on_load lifecycle method."""
        context.on_load()
        assert context.state == PluginState.LOADED

    def test_lifecycle_on_activate(self, context):
        """Test on_activate lifecycle method."""
        context.on_load()
        context.on_activate()
        assert context.state == PluginState.ACTIVE

    def test_lifecycle_on_suspend(self, context):
        """Test on_suspend lifecycle method."""
        context.on_load()
        context.on_activate()
        context.on_suspend()
        assert context.state == PluginState.SUSPENDED

    def test_lifecycle_on_unload(self, context):
        """Test on_unload lifecycle method."""
        context.on_load()
        context.on_unload()
        assert context.state == PluginState.UNLOADED

    def test_lifecycle_on_error(self, context):
        """Test on_error lifecycle method."""
        context.on_error(ValueError("test error"))
        assert context.state == PluginState.ERROR

    def test_emit_event(self, context):
        """Test event emission."""
        event = context.emit_event("test_event", {"key": "value"})
        assert event is not None
        assert "plugin_id" in event.payload
        assert "plugin_name" in event.payload

    def test_subscribe_unsubscribe(self, context):
        """Test subscription management."""
        handler = MagicMock()
        sub_id = context.subscribe(handler)
        assert sub_id is not None
        assert len(context._subscriptions) == 1

        result = context.unsubscribe(sub_id)
        assert result is True
        assert len(context._subscriptions) == 0

    def test_unsubscribe_all(self, context):
        """Test unsubscribe all."""
        handler = MagicMock()
        context.subscribe(handler)
        context.subscribe(handler)
        assert len(context._subscriptions) == 2

        context.unsubscribe_all()
        assert len(context._subscriptions) == 0

    def test_protected_call_success(self, context):
        """Test protected call on success."""

        def success_func():
            return "result"

        result = context.protected_call(success_func)
        assert result == "result"

    def test_protected_call_with_fallback(self, context):
        """Test protected call with fallback on failure."""

        def failing_func():
            raise ValueError("error")

        def fallback():
            return "fallback"

        # Record enough failures to open circuit
        for _ in range(5):
            try:
                context.protected_call(failing_func, fallback=fallback)
            except Exception:
                pass

        # Next call should use fallback if circuit is open
        result = context.protected_call(failing_func, fallback=fallback)
        assert result == "fallback"

    def test_circuit_state(self, context):
        """Test circuit breaker state access."""
        state = context.get_circuit_state()
        assert state in ["closed", "open", "half_open"]

    def test_reset_circuit(self, context):
        """Test circuit breaker reset."""
        context.reset_circuit()
        assert context.get_circuit_state() == "closed"

    def test_watchdog_operations(self, context):
        """Test watchdog start/stop."""
        context.start_operation("test-op")
        assert context.get_watchdog_state() == "monitoring"

        elapsed = context.stop_operation()
        assert elapsed >= 0
        assert context.get_watchdog_state() == "idle"

    def test_pet_watchdog(self, context):
        """Test pet watchdog."""
        context.start_operation("test-op")
        context.pet_watchdog()
        # Should not raise
        context.stop_operation()

    def test_config_without_schema(self, context):
        """Test configuration without schema."""
        result = context.set_config({"key": "value"})
        assert result.valid is True
        assert context.get_config("key") == "value"

    def test_config_with_schema_valid(self, context):
        """Test configuration with valid schema."""
        schema = ObjectSchema(
            name="config",
            properties={
                "host": FieldSchema(
                    name="host", field_type=FieldType.STRING, required=True
                ),
                "port": FieldSchema(
                    name="port", field_type=FieldType.INTEGER, required=True
                ),
            },
        )
        context.set_config_schema(schema)

        result = context.set_config({"host": "localhost", "port": 8080})
        assert result.valid is True
        assert context.get_config("host") == "localhost"
        assert context.get_config("port") == 8080

    def test_config_with_schema_invalid(self, context):
        """Test configuration with invalid schema."""
        schema = ObjectSchema(
            name="config",
            properties={
                "port": FieldSchema(
                    name="port", field_type=FieldType.INTEGER, required=True
                ),
            },
        )
        context.set_config_schema(schema)

        result = context.set_config({"port": "not-a-number"})
        assert result.valid is False
        assert len(result.errors) > 0

    def test_get_config_default(self, context):
        """Test get_config with default."""
        result = context.get_config("nonexistent", "default")
        assert result == "default"

    def test_get_all_config(self, context):
        """Test get_all_config."""
        context.set_config({"a": 1, "b": 2})
        config = context.get_all_config()
        assert config == {"a": 1, "b": 2}

    def test_get_status(self, context):
        """Test get_status returns comprehensive info."""
        context.on_load()
        status = context.get_status()

        assert "info" in status
        assert "state" in status
        assert "created_at" in status
        assert "circuit_breaker" in status
        assert "watchdog" in status
        assert "config_keys" in status
        assert "subscription_count" in status

        assert status["state"] == "loaded"


class TestCreatePluginContext:
    """Tests for create_plugin_context helper."""

    def test_create_with_defaults(self):
        """Test creation with defaults."""
        ctx = create_plugin_context("my-plugin")
        assert ctx.info.name == "my-plugin"
        assert ctx.info.version == "1.0.0"
        assert ctx.state == PluginState.UNLOADED

    def test_create_with_version(self):
        """Test creation with custom version."""
        ctx = create_plugin_context("my-plugin", version="2.0.0")
        assert ctx.info.version == "2.0.0"

    def test_create_with_circuit_config(self):
        """Test creation with custom circuit config."""
        config = CircuitConfig(failure_threshold=5)
        ctx = create_plugin_context("my-plugin", circuit_config=config)
        assert ctx._circuit_breaker.config.failure_threshold == 5
