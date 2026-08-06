# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""
[P3xx] Unit tests for learning modules.
Tests: experience_replay.py, feedback.py
"""

import os
import tempfile
import unittest
from datetime import datetime
from unittest import mock

from warm_logic.kernel.learning.experience_replay import (
    Experience,
    ExperienceReplayBuffer,
    Pattern,
    get_experience_buffer,
)
from warm_logic.kernel.learning.feedback import (
    Correction,
    FeedbackMemory,
    Preference,
    PreferenceTracker,
    get_feedback_memory,
    get_preference_tracker,
)


class TestExperience(unittest.TestCase):
    """Test Experience dataclass."""

    def test_experience_creation(self):
        """Test creating an Experience."""
        exp = Experience(
            id="EXP001",
            timestamp=datetime.now(),
            context="user asked about Python",
            action="provided code example",
            outcome="user satisfied",
            success=True,
            reward=1.0,
            tags=["code", "python"],
        )
        self.assertEqual(exp.id, "EXP001")
        self.assertTrue(exp.success)
        self.assertEqual(exp.reward, 1.0)

    def test_experience_default_tags(self):
        """Test Experience with default empty tags."""
        exp = Experience(
            id="EXP002",
            timestamp=datetime.now(),
            context="test",
            action="test",
            outcome="test",
            success=False,
            reward=-0.5,
        )
        self.assertEqual(exp.tags, [])


class TestPattern(unittest.TestCase):
    """Test Pattern dataclass."""

    def test_pattern_creation(self):
        """Test creating a Pattern."""
        pat = Pattern(
            id="PAT001",
            trigger="user asks for code",
            response="provide example",
            confidence=0.8,
            occurrences=5,
            last_success_rate=0.9,
        )
        self.assertEqual(pat.id, "PAT001")
        self.assertEqual(pat.confidence, 0.8)


class TestExperienceReplayBuffer(unittest.TestCase):
    """Test ExperienceReplayBuffer."""

    def setUp(self):
        """Create buffer with temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.buffer = ExperienceReplayBuffer(
            storage_path=self.temp_dir, max_experiences=100
        )

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_buffer_init(self):
        """Test buffer initialization."""
        self.assertEqual(len(self.buffer.experiences), 0)
        self.assertEqual(len(self.buffer.patterns), 0)

    def test_record_experience(self):
        """Test recording an experience."""
        exp = self.buffer.record(
            context="test context",
            action="test action",
            outcome="test outcome",
            success=True,
            reward=1.0,
        )
        self.assertIsNotNone(exp)
        self.assertTrue(exp.success)
        self.assertEqual(len(self.buffer.experiences), 1)

    def test_record_experience_default_reward(self):
        """Test default reward calculation."""
        exp_success = self.buffer.record(
            context="test", action="act", outcome="ok", success=True
        )
        self.assertEqual(exp_success.reward, 1.0)

        exp_fail = self.buffer.record(
            context="test", action="act", outcome="fail", success=False
        )
        self.assertEqual(exp_fail.reward, -0.5)

    def test_recall_empty(self):
        """Test recall with empty buffer."""
        results = self.buffer.recall("any context")
        self.assertEqual(results, [])

    def test_recall_matching(self):
        """Test recall finds matching experiences."""
        self.buffer.record(
            context="python programming tutorial",
            action="showed code",
            outcome="learned",
            success=True,
        )
        results = self.buffer.recall("python tutorial")
        self.assertEqual(len(results), 1)

    def test_suggest_no_data(self):
        """Test suggest with no data."""
        result = self.buffer.suggest("any context")
        self.assertIsNone(result)

    def test_get_stats_empty(self):
        """Test stats with empty buffer."""
        stats = self.buffer.get_stats()
        self.assertEqual(stats["experiences"], 0)
        self.assertEqual(stats["patterns"], 0)

    def test_max_experiences_trim(self):
        """Test buffer trims at max capacity."""
        small_buffer = ExperienceReplayBuffer(
            storage_path=self.temp_dir + "/small", max_experiences=5
        )
        for i in range(10):
            small_buffer.record(
                context=f"ctx{i}", action="act", outcome="out", success=True
            )
        self.assertLessEqual(len(small_buffer.experiences), 5)

    def test_env_variable_path(self):
        """Test environment variable for storage path."""
        with mock.patch.dict(os.environ, {"WL_EXPERIENCE_PATH": self.temp_dir}):
            buffer = ExperienceReplayBuffer()
            self.assertEqual(buffer.storage_path, self.temp_dir)


class TestCorrection(unittest.TestCase):
    """Test Correction dataclass."""

    def test_correction_creation(self):
        """Test creating a Correction."""
        corr = Correction(
            id="COR001",
            timestamp=datetime.now(),
            original="english",
            corrected="한글",
            category="language",
        )
        self.assertEqual(corr.id, "COR001")
        self.assertEqual(corr.applied, 0)


class TestPreference(unittest.TestCase):
    """Test Preference dataclass."""

    def test_preference_creation(self):
        """Test creating a Preference."""
        pref = Preference(
            key="language",
            value="korean",
            confidence=0.8,
            observations=5,
            last_updated=datetime.now(),
        )
        self.assertEqual(pref.key, "language")
        self.assertEqual(pref.value, "korean")


class TestFeedbackMemory(unittest.TestCase):
    """Test FeedbackMemory."""

    def setUp(self):
        """Create memory with temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory = FeedbackMemory(storage_path=self.temp_dir)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_memory_init(self):
        """Test memory initialization."""
        self.assertEqual(len(self.memory.corrections), 0)

    def test_record_correction(self):
        """Test recording a correction."""
        corr = self.memory.record_correction(
            original="do it in English",
            corrected="한글로 해줘",
            category="language",
        )
        self.assertIsNotNone(corr)
        self.assertEqual(len(self.memory.corrections), 1)

    def test_apply_corrections(self):
        """Test applying corrections."""
        self.memory.record_correction(original="foo", corrected="bar", category="style")
        result, applied = self.memory.apply_corrections("this is foo test")
        self.assertEqual(result, "this is bar test")
        self.assertEqual(len(applied), 1)

    def test_get_category_rules(self):
        """Test filtering by category."""
        self.memory.record_correction("a", "b", "code")
        self.memory.record_correction("c", "d", "style")
        code_rules = self.memory.get_category_rules("code")
        self.assertEqual(len(code_rules), 1)

    def test_env_variable_path(self):
        """Test environment variable for storage path."""
        with mock.patch.dict(os.environ, {"WL_FEEDBACK_PATH": self.temp_dir}):
            memory = FeedbackMemory()
            self.assertEqual(memory.storage_path, self.temp_dir)


class TestPreferenceTracker(unittest.TestCase):
    """Test PreferenceTracker."""

    def setUp(self):
        """Create tracker with temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.tracker = PreferenceTracker(storage_path=self.temp_dir)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tracker_init(self):
        """Test tracker initialization."""
        self.assertEqual(len(self.tracker.preferences), 0)

    def test_observe_new_preference(self):
        """Test observing a new preference."""
        self.tracker.observe("language", "korean", weight=1.0)
        self.assertEqual(len(self.tracker.preferences), 1)

    def test_observe_strengthen_preference(self):
        """Test strengthening existing preference."""
        self.tracker.observe("language", "korean", weight=1.0)
        initial_conf = self.tracker.preferences["language"].confidence
        self.tracker.observe("language", "korean", weight=1.0)
        new_conf = self.tracker.preferences["language"].confidence
        self.assertGreater(new_conf, initial_conf)

    def test_get_preference(self):
        """Test getting a preference."""
        self.tracker.observe("code_style", "concise")
        value, confidence = self.tracker.get("code_style")
        self.assertEqual(value, "concise")
        self.assertGreater(confidence, 0)

    def test_get_missing_preference(self):
        """Test getting missing preference."""
        value, confidence = self.tracker.get("missing", default="default")
        self.assertEqual(value, "default")
        self.assertEqual(confidence, 0.0)

    def test_get_all_preferences(self):
        """Test getting all preferences."""
        self.tracker.observe("a", "1")
        self.tracker.observe("b", "2")
        all_prefs = self.tracker.get_all()
        self.assertEqual(len(all_prefs), 2)

    def test_env_variable_path(self):
        """Test environment variable for storage path."""
        with mock.patch.dict(os.environ, {"WL_PREFS_PATH": self.temp_dir}):
            tracker = PreferenceTracker()
            self.assertEqual(tracker.storage_path, self.temp_dir)


class TestConvenienceFunctions(unittest.TestCase):
    """Test module convenience functions."""

    def test_get_experience_buffer(self):
        """Test get_experience_buffer function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = get_experience_buffer(tmpdir)
            self.assertIsInstance(buffer, ExperienceReplayBuffer)

    def test_get_feedback_memory(self):
        """Test get_feedback_memory function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = get_feedback_memory(tmpdir)
            self.assertIsInstance(memory, FeedbackMemory)

    def test_get_preference_tracker(self):
        """Test get_preference_tracker function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = get_preference_tracker(tmpdir)
            self.assertIsInstance(tracker, PreferenceTracker)


if __name__ == "__main__":
    unittest.main()
