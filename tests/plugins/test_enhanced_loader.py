# ==========================================================
# Tests: enhanced_loader.py
# ==========================================================
"""Tests for fault-tolerant plugin loader."""

import pytest
from unittest.mock import MagicMock, patch

from warm_logic_core.plugins.enhanced_loader import (
    PluginLoader,
    PluginLoadResult,
    PluginLoadError,
    PluginManifest,
    LoadStatus,
    PluginProtocol,
)
from warm_logic_core.plugins.plugin_context import PluginContext, PluginState


class TestPluginManifest:
    """Tests for PluginManifest dataclass."""

    def test_create_manifest(self):
        """Test manifest creation."""
        manifest = PluginManifest(
            name="test-plugin",
            version="1.0.0",
            entry_point="test.module:Plugin",
            author="Test Author",
            description="Test plugin",
        )
        assert manifest.name == "test-plugin"
        assert manifest.version == "1.0.0"
        assert manifest.entry_point == "test.module:Plugin"

    def test_from_dict(self):
        """Test manifest from dictionary."""
        data = {
            "name": "my-plugin",
            "version": "2.0.0",
            "entry_point": "pkg:Class",
            "author": "author",
            "description": "desc",
            "dependencies": ["dep1"],
            "capabilities": ["cap1"],
        }
        manifest = PluginManifest.from_dict(data)
        assert manifest.name == "my-plugin"
        assert manifest.version == "2.0.0"
        assert manifest.dependencies == ["dep1"]
        assert manifest.capabilities == ["cap1"]

    def test_from_dict_defaults(self):
        """Test from_dict with defaults."""
        data = {"name": "minimal"}
        manifest = PluginManifest.from_dict(data)
        assert manifest.name == "minimal"
        assert manifest.version == "1.0.0"
        assert manifest.dependencies == []


class TestPluginLoadResult:
    """Tests for PluginLoadResult dataclass."""

    def test_success_result(self):
        """Test success result."""
        result = PluginLoadResult(
            plugin_name="test",
            status=LoadStatus.SUCCESS,
            load_time_ms=50.0,
            attempts=1,
        )
        assert result.status == LoadStatus.SUCCESS
        assert result.load_time_ms == 50.0

    def test_failed_result(self):
        """Test failed result."""
        result = PluginLoadResult(
            plugin_name="test",
            status=LoadStatus.FAILED,
            error="Load error",
            attempts=3,
        )
        assert result.status == LoadStatus.FAILED
        assert result.error == "Load error"

    def test_to_dict(self):
        """Test serialization."""
        result = PluginLoadResult(
            plugin_name="test",
            status=LoadStatus.SUCCESS,
            load_time_ms=100.0,
        )
        data = result.to_dict()
        assert data["plugin_name"] == "test"
        assert data["status"] == "success"
        assert data["load_time_ms"] == 100.0
        assert "timestamp" in data


class TestPluginLoadError:
    """Tests for PluginLoadError exception."""

    def test_error_message(self):
        """Test error message format."""
        error = PluginLoadError("test-plugin", "Import failed", ValueError("cause"))
        assert "test-plugin" in str(error)
        assert "Import failed" in str(error)
        assert error.plugin_name == "test-plugin"
        assert error.reason == "Import failed"
        assert isinstance(error.cause, ValueError)


class MockPlugin:
    """Mock plugin for testing."""

    def __init__(self):
        self.loaded = False
        self.unloaded = False

    def on_load(self, context: PluginContext) -> None:
        self.loaded = True

    def on_unload(self) -> None:
        self.unloaded = True


class FailingPlugin:
    """Plugin that fails on load."""

    def on_load(self, context: PluginContext) -> None:
        raise ValueError("Intentional failure")

    def on_unload(self) -> None:
        pass


class TestPluginLoader:
    """Tests for PluginLoader class."""

    @pytest.fixture
    def loader(self):
        """Create test loader."""
        return PluginLoader(max_retries=2, retry_backoff_ms=10)

    @pytest.fixture
    def manifest(self):
        """Create test manifest."""
        return PluginManifest(name="test-plugin", version="1.0.0")

    def test_load_plugin_success(self, loader, manifest):
        """Test successful plugin loading."""
        result = loader.load_plugin(manifest, MockPlugin)
        assert result.status == LoadStatus.SUCCESS
        assert result.context is not None
        assert result.context.state == PluginState.LOADED
        assert result.attempts == 1

    def test_load_plugin_failure(self, loader, manifest):
        """Test plugin loading failure."""
        result = loader.load_plugin(manifest, FailingPlugin)
        assert result.status == LoadStatus.FAILED
        assert result.error is not None
        assert result.attempts == 2  # max_retries

    def test_load_plugin_without_class(self, loader, manifest):
        """Test loading plugin without class (no entry point)."""
        result = loader.load_plugin(manifest)
        assert result.status == LoadStatus.SUCCESS
        # Context created but no plugin instance

    def test_quarantine_on_repeated_failures(self, loader, manifest):
        """Test quarantine after repeated failures."""
        # First load attempt (fails)
        result1 = loader.load_plugin(manifest, FailingPlugin)
        assert result1.status == LoadStatus.FAILED

        # Second attempt should be quarantined
        result2 = loader.load_plugin(manifest, FailingPlugin)
        assert result2.status == LoadStatus.QUARANTINED

    def test_unquarantine(self, loader, manifest):
        """Test unquarantine functionality."""
        # Quarantine plugin
        loader.load_plugin(manifest, FailingPlugin)
        loader.load_plugin(manifest, FailingPlugin)

        # Verify quarantined
        assert manifest.name in loader.get_quarantined()

        # Unquarantine
        result = loader.unquarantine(manifest.name)
        assert result is True
        assert manifest.name not in loader.get_quarantined()

    def test_unquarantine_nonexistent(self, loader):
        """Test unquarantine nonexistent plugin."""
        result = loader.unquarantine("nonexistent")
        assert result is False

    def test_unload_plugin(self, loader, manifest):
        """Test plugin unloading."""
        loader.load_plugin(manifest, MockPlugin)
        assert manifest.name in loader.get_loaded_plugins()

        result = loader.unload_plugin(manifest.name)
        assert result is True
        assert manifest.name not in loader.get_loaded_plugins()

    def test_unload_nonexistent(self, loader):
        """Test unloading nonexistent plugin."""
        result = loader.unload_plugin("nonexistent")
        assert result is False

    def test_get_loaded_plugins(self, loader):
        """Test getting loaded plugins."""
        m1 = PluginManifest(name="plugin1")
        m2 = PluginManifest(name="plugin2")

        loader.load_plugin(m1, MockPlugin)
        loader.load_plugin(m2, MockPlugin)

        loaded = loader.get_loaded_plugins()
        assert len(loaded) == 2
        assert "plugin1" in loaded
        assert "plugin2" in loaded

    def test_get_load_history(self, loader, manifest):
        """Test getting load history."""
        loader.load_plugin(manifest, MockPlugin)

        history = loader.get_load_history()
        assert len(history) == 1
        assert history[0].plugin_name == "test-plugin"
        assert history[0].status == LoadStatus.SUCCESS

    def test_get_load_history_limit(self, loader):
        """Test load history limit."""
        for i in range(10):
            m = PluginManifest(name=f"plugin-{i}")
            loader.load_plugin(m, MockPlugin)

        history = loader.get_load_history(limit=5)
        assert len(history) == 5

    def test_get_stats(self, loader, manifest):
        """Test loader statistics."""
        loader.load_plugin(manifest, MockPlugin)

        stats = loader.get_stats()
        assert stats["loaded_count"] == 1
        assert stats["quarantined_count"] == 0
        assert stats["total_loads"] == 1
        assert stats["success_count"] == 1
        assert stats["failed_count"] == 0
        assert stats["success_rate"] == 1.0

    def test_load_time_recorded(self, loader, manifest):
        """Test load time is recorded."""
        result = loader.load_plugin(manifest, MockPlugin)
        assert result.load_time_ms > 0


class TestPluginLoaderEntryPoint:
    """Tests for entry point loading."""

    @pytest.fixture
    def loader(self):
        """Create test loader."""
        return PluginLoader()

    def test_import_invalid_entry_point(self, loader):
        """Test importing invalid entry point."""
        manifest = PluginManifest(name="test", entry_point="nonexistent.module:Plugin")
        result = loader.load_plugin(manifest)
        assert result.status == LoadStatus.FAILED
        assert "import" in result.error.lower() or "failed" in result.error.lower()

    def test_entry_point_with_colon(self, loader):
        """Test entry point parsing with colon."""
        # This will fail but tests the parsing
        manifest = PluginManifest(name="test", entry_point="some.module:ClassName")
        result = loader.load_plugin(manifest)
        assert result.status == LoadStatus.FAILED

    def test_entry_point_without_colon(self, loader):
        """Test entry point parsing without colon."""
        # This will fail but tests the parsing
        manifest = PluginManifest(name="test", entry_point="some.module")
        result = loader.load_plugin(manifest)
        assert result.status == LoadStatus.FAILED
