# ==========================================================
# Tests: plugin_registry.py
# ==========================================================
"""Tests for plugin registry with dependency management."""

import json
import pytest
import tempfile
from pathlib import Path

from warm_logic_core.plugins.plugin_registry import (
    PluginRegistry,
    PluginEntry,
    RegistryError,
)


class TestPluginEntry:
    """Tests for PluginEntry dataclass."""

    def test_create_generates_id(self):
        """Test that create generates a unique plugin ID."""
        entry = PluginEntry.create("test-plugin", "1.0.0")
        assert entry.plugin_id.startswith("PLUGIN-")
        assert entry.name == "test-plugin"
        assert entry.version == "1.0.0"
        assert entry.enabled is True

    def test_to_dict_serialization(self):
        """Test serialization to dictionary."""
        entry = PluginEntry(
            plugin_id="PLUGIN-TEST",
            name="test",
            version="2.0.0",
            entry_point="test.module:Plugin",
            enabled=True,
            dependencies=["dep1"],
            dependents=["dep2"],
            metadata={"key": "value"},
        )
        data = entry.to_dict()
        assert data["plugin_id"] == "PLUGIN-TEST"
        assert data["name"] == "test"
        assert data["version"] == "2.0.0"
        assert data["entry_point"] == "test.module:Plugin"
        assert data["dependencies"] == ["dep1"]
        assert data["dependents"] == ["dep2"]
        assert data["metadata"] == {"key": "value"}

    def test_from_dict_deserialization(self):
        """Test deserialization from dictionary."""
        data = {
            "plugin_id": "PLUGIN-ABC",
            "name": "my-plugin",
            "version": "1.5.0",
            "entry_point": "pkg:Class",
            "enabled": False,
            "dependencies": ["a", "b"],
            "metadata": {"x": 1},
        }
        entry = PluginEntry.from_dict(data)
        assert entry.plugin_id == "PLUGIN-ABC"
        assert entry.name == "my-plugin"
        assert entry.version == "1.5.0"
        assert entry.enabled is False
        assert entry.dependencies == ["a", "b"]

    def test_from_dict_defaults(self):
        """Test from_dict with missing fields."""
        data = {"name": "minimal"}
        entry = PluginEntry.from_dict(data)
        assert entry.name == "minimal"
        assert entry.version == "1.0.0"
        assert entry.enabled is True
        assert entry.dependencies == []


class TestPluginRegistry:
    """Tests for PluginRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create test registry."""
        return PluginRegistry()

    @pytest.fixture
    def temp_path(self):
        """Create temporary file path."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            return Path(f.name)

    def test_register_plugin(self, registry):
        """Test basic plugin registration."""
        entry = PluginEntry.create("test-plugin")
        registry.register(entry)

        result = registry.get("test-plugin")
        assert result is not None
        assert result.name == "test-plugin"

    def test_register_duplicate_version_fails(self, registry):
        """Test registering same version fails."""
        entry1 = PluginEntry.create("test-plugin", "1.0.0")
        registry.register(entry1)

        entry2 = PluginEntry.create("test-plugin", "1.0.0")
        with pytest.raises(RegistryError) as exc:
            registry.register(entry2)
        assert "already registered" in str(exc.value)

    def test_register_different_versions(self, registry):
        """Test registering different versions updates entry."""
        entry1 = PluginEntry.create("test-plugin", "1.0.0")
        registry.register(entry1)

        entry2 = PluginEntry.create("test-plugin", "2.0.0")
        registry.register(entry2)

        result = registry.get("test-plugin")
        assert result.version == "2.0.0"

    def test_register_with_missing_dependency_fails(self, registry):
        """Test registration fails with missing dependency."""
        entry = PluginEntry.create("test-plugin")
        entry.dependencies = ["nonexistent"]

        with pytest.raises(RegistryError) as exc:
            registry.register(entry)
        assert "Missing dependencies" in str(exc.value)

    def test_register_with_dependency(self, registry):
        """Test registration with satisfied dependency."""
        dep = PluginEntry.create("dep-plugin")
        registry.register(dep)

        entry = PluginEntry.create("test-plugin")
        entry.dependencies = ["dep-plugin"]
        registry.register(entry)

        # Check dependent was updated
        dep_result = registry.get("dep-plugin")
        assert "test-plugin" in dep_result.dependents

    def test_register_skip_dependency_check(self, registry):
        """Test registration with dependency check disabled."""
        entry = PluginEntry.create("test-plugin")
        entry.dependencies = ["nonexistent"]

        registry.register(entry, check_dependencies=False)
        assert registry.get("test-plugin") is not None

    def test_unregister_plugin(self, registry):
        """Test plugin unregistration."""
        entry = PluginEntry.create("test-plugin")
        registry.register(entry)

        result = registry.unregister("test-plugin")
        assert result is True
        assert registry.get("test-plugin") is None

    def test_unregister_nonexistent(self, registry):
        """Test unregistering nonexistent plugin."""
        result = registry.unregister("nonexistent")
        assert result is False

    def test_unregister_with_dependents_fails(self, registry):
        """Test unregistering with dependents fails."""
        dep = PluginEntry.create("dep-plugin")
        registry.register(dep)

        entry = PluginEntry.create("test-plugin")
        entry.dependencies = ["dep-plugin"]
        registry.register(entry)

        with pytest.raises(RegistryError) as exc:
            registry.unregister("dep-plugin")
        assert "has dependents" in str(exc.value)

    def test_unregister_with_dependents_force(self, registry):
        """Test force unregister with dependents."""
        dep = PluginEntry.create("dep-plugin")
        registry.register(dep)

        entry = PluginEntry.create("test-plugin")
        entry.dependencies = ["dep-plugin"]
        registry.register(entry)

        result = registry.unregister("dep-plugin", force=True)
        assert result is True
        assert registry.get("dep-plugin") is None

    def test_get_all(self, registry):
        """Test getting all plugins."""
        registry.register(PluginEntry.create("plugin1"))
        registry.register(PluginEntry.create("plugin2"))
        registry.register(PluginEntry.create("plugin3"))

        all_plugins = registry.get_all()
        assert len(all_plugins) == 3
        names = {p.name for p in all_plugins}
        assert names == {"plugin1", "plugin2", "plugin3"}

    def test_get_enabled(self, registry):
        """Test getting enabled plugins."""
        registry.register(PluginEntry.create("plugin1"))
        registry.register(PluginEntry.create("plugin2"))
        registry.disable("plugin2")

        enabled = registry.get_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "plugin1"

    def test_enable_disable(self, registry):
        """Test enable/disable functionality."""
        registry.register(PluginEntry.create("plugin1"))

        registry.disable("plugin1")
        assert registry.get("plugin1").enabled is False

        registry.enable("plugin1")
        assert registry.get("plugin1").enabled is True

    def test_enable_nonexistent(self, registry):
        """Test enabling nonexistent plugin."""
        result = registry.enable("nonexistent")
        assert result is False

    def test_disable_nonexistent(self, registry):
        """Test disabling nonexistent plugin."""
        result = registry.disable("nonexistent")
        assert result is False

    def test_get_load_order_no_dependencies(self, registry):
        """Test load order with no dependencies."""
        registry.register(PluginEntry.create("a"))
        registry.register(PluginEntry.create("b"))
        registry.register(PluginEntry.create("c"))

        order = registry.get_load_order()
        assert len(order) == 3
        assert set(order) == {"a", "b", "c"}

    def test_get_load_order_with_dependencies(self, registry):
        """Test load order respects dependencies."""
        # Register in reverse order
        c = PluginEntry.create("c")
        c.dependencies = ["b"]
        b = PluginEntry.create("b")
        b.dependencies = ["a"]
        a = PluginEntry.create("a")

        registry.register(a)
        registry.register(b, check_dependencies=True)
        registry.register(c, check_dependencies=True)

        order = registry.get_load_order()
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_get_stats(self, registry):
        """Test registry statistics."""
        registry.register(PluginEntry.create("plugin1"))
        registry.register(PluginEntry.create("plugin2"))
        registry.disable("plugin2")

        stats = registry.get_stats()
        assert stats["total_plugins"] == 2
        assert stats["enabled_count"] == 1
        assert stats["disabled_count"] == 1
        assert "registry_id" in stats


class TestPluginRegistryPersistence:
    """Tests for registry persistence."""

    @pytest.fixture
    def temp_path(self):
        """Create temporary file path."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        path.unlink()  # Remove so registry creates it
        yield path
        if path.exists():
            path.unlink()

    def test_persist_and_load(self, temp_path):
        """Test persistence and loading."""
        # Create and populate registry
        reg1 = PluginRegistry(persist_path=temp_path)
        reg1.register(PluginEntry.create("plugin1", "1.0.0"))
        reg1.register(PluginEntry.create("plugin2", "2.0.0"))

        # Create new registry from same path
        reg2 = PluginRegistry(persist_path=temp_path)

        assert reg2.get("plugin1") is not None
        assert reg2.get("plugin2") is not None
        assert reg2.get("plugin1").version == "1.0.0"
        assert reg2.get("plugin2").version == "2.0.0"

    def test_persist_file_format(self, temp_path):
        """Test persistence file format."""
        reg = PluginRegistry(persist_path=temp_path)
        reg.register(PluginEntry.create("test", "1.0.0"))

        with open(temp_path) as f:
            data = json.load(f)

        assert "schema_version" in data
        assert "registry_id" in data
        assert "updated_at" in data
        assert "plugins" in data
        assert "test" in data["plugins"]

    def test_corrupt_file_handled(self, temp_path):
        """Test handling of corrupt persistence file."""
        # Write corrupt data
        temp_path.write_text("not valid json")

        # Should not raise, just ignore
        reg = PluginRegistry(persist_path=temp_path)
        assert reg.get_all() == []
