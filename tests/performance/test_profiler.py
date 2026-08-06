"""Tests for Profiler module."""

from __future__ import annotations

import time

import pytest

from warm_logic_core.performance.profiler import (
    ProfileSection,
    ProfileResult,
    Profiler,
    profile_function,
)


class TestProfileSection:
    """Tests for ProfileSection."""

    def test_section_creation(self):
        """Test section creation."""
        section = ProfileSection.create("test_section")

        assert section.section_id.startswith("SEC-")
        assert section.name == "test_section"
        assert section.start_time > 0
        assert section.is_running() is True

    def test_section_with_parent(self):
        """Test section with parent."""
        section = ProfileSection.create("child", parent_id="PARENT-123")

        assert section.parent_id == "PARENT-123"

    def test_section_stop(self):
        """Test stopping section."""
        section = ProfileSection.create("test")
        time.sleep(0.01)
        section.stop()

        assert section.is_running() is False
        assert section.end_time is not None
        assert section.elapsed_ms >= 10.0

    def test_section_to_dict(self):
        """Test section serialization."""
        section = ProfileSection.create("test")
        section.stop()

        data = section.to_dict()

        assert data["name"] == "test"
        assert "elapsed_ms" in data
        assert data["section_id"].startswith("SEC-")


class TestProfileResult:
    """Tests for ProfileResult."""

    def test_result_creation(self):
        """Test result creation."""
        result = ProfileResult.create()

        assert result.result_id.startswith("PROF-")
        assert result.total_time_ms == 0.0
        assert len(result.sections) == 0

    def test_result_get_sections_by_name(self):
        """Test getting sections by name."""
        result = ProfileResult.create()

        section1 = ProfileSection.create("test")
        section1.stop()
        section2 = ProfileSection.create("test")
        section2.stop()
        section3 = ProfileSection.create("other")
        section3.stop()

        result.sections = [section1, section2, section3]

        test_sections = result.get_sections_by_name("test")

        assert len(test_sections) == 2

    def test_result_get_total_time_for(self):
        """Test getting total time for name."""
        result = ProfileResult.create()

        section1 = ProfileSection(section_id="SEC-1", name="test", elapsed_ms=10.0)
        section2 = ProfileSection(section_id="SEC-2", name="test", elapsed_ms=20.0)

        result.sections = [section1, section2]

        total = result.get_total_time_for("test")

        assert total == 30.0

    def test_result_get_call_count(self):
        """Test getting call count."""
        result = ProfileResult.create()
        result.call_counts = {"test": 5, "other": 3}

        assert result.get_call_count("test") == 5
        assert result.get_call_count("nonexistent") == 0

    def test_result_get_hotspots(self):
        """Test getting hotspots."""
        result = ProfileResult.create()
        result.total_time_ms = 100.0
        result.sections = [
            ProfileSection(section_id="SEC-1", name="slow", elapsed_ms=50.0),
            ProfileSection(section_id="SEC-2", name="medium", elapsed_ms=30.0),
            ProfileSection(section_id="SEC-3", name="fast", elapsed_ms=20.0),
        ]

        hotspots = result.get_hotspots(limit=2)

        assert len(hotspots) == 2
        assert hotspots[0]["name"] == "slow"
        assert hotspots[0]["percentage"] == 50.0
        assert hotspots[1]["name"] == "medium"

    def test_result_to_dict(self):
        """Test result serialization."""
        result = ProfileResult.create()
        result.total_time_ms = 100.0

        data = result.to_dict()

        assert data["schema_version"] == "profile_result_v1"
        assert data["total_time_ms"] == 100.0


class TestProfiler:
    """Tests for Profiler."""

    def test_profiler_initialization(self):
        """Test profiler initialization."""
        profiler = Profiler()

        assert profiler.profiler_id.startswith("PROFILER-")
        assert profiler.enabled is True

    def test_profiler_custom_id(self):
        """Test profiler with custom ID."""
        profiler = Profiler(profiler_id="TEST-PROFILER")

        assert profiler.profiler_id == "TEST-PROFILER"

    def test_profiler_disabled(self):
        """Test disabled profiler."""
        profiler = Profiler(enabled=False)
        profiler.start()

        section = profiler.begin_section("test")
        profiler.end_section()

        result = profiler.stop()

        assert len(result.sections) == 0

    def test_profiler_start_stop(self):
        """Test profiler start and stop."""
        profiler = Profiler()
        profiler.start()

        time.sleep(0.01)

        result = profiler.stop()

        assert result.total_time_ms >= 10.0

    def test_profiler_begin_end_section(self):
        """Test begin and end section."""
        profiler = Profiler()
        profiler.start()

        section = profiler.begin_section("test")
        time.sleep(0.01)
        profiler.end_section()

        result = profiler.stop()

        assert len(result.sections) == 1
        assert result.sections[0].name == "test"
        assert result.sections[0].elapsed_ms >= 10.0

    def test_profiler_nested_sections(self):
        """Test nested sections."""
        profiler = Profiler()
        profiler.start()

        profiler.begin_section("outer")
        profiler.begin_section("inner")
        profiler.end_section("inner")
        profiler.end_section("outer")

        result = profiler.stop()

        outer = result.get_sections_by_name("outer")[0]
        inner = result.get_sections_by_name("inner")[0]

        assert inner.parent_id == outer.section_id

    def test_profiler_context_manager(self):
        """Test section context manager."""
        profiler = Profiler()
        profiler.start()

        with profiler.section("test") as section:
            time.sleep(0.01)

        result = profiler.stop()

        assert len(result.sections) == 1
        assert result.sections[0].elapsed_ms >= 10.0

    def test_profiler_decorator(self):
        """Test profiler decorator."""
        profiler = Profiler()

        @profiler.profile()
        def test_func():
            time.sleep(0.01)
            return 42

        profiler.start()
        result = test_func()
        prof_result = profiler.stop()

        assert result == 42
        assert len(prof_result.sections) == 1
        assert prof_result.sections[0].name == "test_func"

    def test_profiler_decorator_custom_name(self):
        """Test profiler decorator with custom name."""
        profiler = Profiler()

        @profiler.profile("custom_name")
        def test_func():
            pass

        profiler.start()
        test_func()
        result = profiler.stop()

        assert result.sections[0].name == "custom_name"

    def test_profiler_call_counts(self):
        """Test call counting."""
        profiler = Profiler()
        profiler.start()

        for _ in range(5):
            with profiler.section("test"):
                pass

        result = profiler.stop()

        assert result.call_counts["test"] == 5

    def test_profiler_get_active_section(self):
        """Test getting active section."""
        profiler = Profiler()
        profiler.start()

        assert profiler.get_active_section() is None

        profiler.begin_section("test")
        active = profiler.get_active_section()

        assert active is not None
        assert active.name == "test"

        profiler.end_section()

        assert profiler.get_active_section() is None

    def test_profiler_get_sections(self):
        """Test getting all sections."""
        profiler = Profiler()
        profiler.start()

        with profiler.section("section1"):
            pass
        with profiler.section("section2"):
            pass

        sections = profiler.get_sections()

        assert len(sections) == 2

    def test_profiler_clear(self):
        """Test clearing profiler."""
        profiler = Profiler()
        profiler.start()

        with profiler.section("test"):
            pass

        profiler.clear()

        assert len(profiler.get_sections()) == 0

    def test_profiler_end_section_by_name(self):
        """Test ending specific section by name."""
        profiler = Profiler()
        profiler.start()

        profiler.begin_section("outer")
        profiler.begin_section("inner")
        profiler.end_section("outer")  # End outer first

        sections = profiler.get_sections()

        # Outer should be stopped
        outer = [s for s in sections if s.name == "outer"][0]
        assert outer.is_running() is False


class TestProfileFunction:
    """Tests for profile_function function."""

    def test_profile_function_simple(self):
        """Test profiling simple function."""

        def add(a, b):
            return a + b

        result = profile_function(add, 1, 2)

        assert len(result.sections) == 1
        assert result.sections[0].name == "add"

    def test_profile_function_multiple_iterations(self):
        """Test profiling with multiple iterations."""

        def slow_func():
            time.sleep(0.001)

        result = profile_function(slow_func, iterations=5)

        assert len(result.sections) == 5
        assert result.call_counts["slow_func"] == 5

    def test_profile_function_with_kwargs(self):
        """Test profiling with keyword arguments."""

        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = profile_function(greet, "World", greeting="Hi")

        assert len(result.sections) == 1


class TestEdgeCases:
    """Edge case tests."""

    def test_profiler_stop_running_sections(self):
        """Test that stop() closes running sections."""
        profiler = Profiler()
        profiler.start()

        profiler.begin_section("test")
        # Don't end section

        result = profiler.stop()

        # Section should still be captured
        assert len(result.sections) == 1
        assert result.sections[0].elapsed_ms >= 0

    def test_profiler_end_section_empty(self):
        """Test ending section with no active sections."""
        profiler = Profiler()
        profiler.start()

        # Should not raise
        profiler.end_section()

        result = profiler.stop()
        assert len(result.sections) == 0

    def test_profiler_end_nonexistent_name(self):
        """Test ending nonexistent section by name."""
        profiler = Profiler()
        profiler.start()

        profiler.begin_section("test")
        profiler.end_section("nonexistent")  # Should not raise

        result = profiler.stop()
        # Original section should still be running
        assert len(result.sections) == 1

    def test_hotspots_zero_total_time(self):
        """Test hotspots with zero total time."""
        result = ProfileResult.create()
        result.total_time_ms = 0.0
        result.sections = [
            ProfileSection(section_id="SEC-1", name="test", elapsed_ms=10.0)
        ]

        hotspots = result.get_hotspots()

        assert hotspots[0]["percentage"] == 0

    def test_disabled_profiler_section_context(self):
        """Test disabled profiler with section context."""
        profiler = Profiler(enabled=False)
        profiler.start()

        with profiler.section("test") as section:
            pass

        result = profiler.stop()

        assert len(result.sections) == 0
