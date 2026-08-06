# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for release management infrastructure."""

import unittest

from warm_logic.infrastructure.release import (
    ArtifactBuilder,
    Changelog,
    ChangelogEntry,
    ChangelogGenerator,
    ChangeType,
    DistributionChannel,
    DistributionManager,
    Release,
    ReleaseArtifact,
    ReleaseManager,
    ReleaseStatus,
    ReleaseType,
    ReleaseValidator,
    SemanticVersion,
    ValidationGate,
    ValidationResult,
    VersionManager,
)


class TestSemanticVersion(unittest.TestCase):
    """Tests for SemanticVersion."""

    def test_default_version(self):
        """Test default version values."""
        version = SemanticVersion()
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)
        self.assertEqual(str(version), "1.0.0")

    def test_version_string(self):
        """Test version string representation."""
        version = SemanticVersion(major=2, minor=3, patch=4)
        self.assertEqual(str(version), "2.3.4")

    def test_version_with_prerelease(self):
        """Test version with prerelease tag."""
        version = SemanticVersion(major=1, minor=0, patch=0, prerelease="rc.1")
        self.assertEqual(str(version), "1.0.0-rc.1")

    def test_version_with_build_metadata(self):
        """Test version with build metadata."""
        version = SemanticVersion(major=1, minor=0, patch=0, build_metadata="build.123")
        self.assertEqual(str(version), "1.0.0+build.123")

    def test_version_full(self):
        """Test full version string."""
        version = SemanticVersion(
            major=1, minor=2, patch=3, prerelease="alpha.1", build_metadata="sha.abc"
        )
        self.assertEqual(str(version), "1.2.3-alpha.1+sha.abc")

    def test_parse_simple(self):
        """Test parsing simple version."""
        version = SemanticVersion.parse("1.2.3")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)

    def test_parse_with_prerelease(self):
        """Test parsing version with prerelease."""
        version = SemanticVersion.parse("1.0.0-beta.2")
        self.assertEqual(version.prerelease, "beta.2")

    def test_parse_with_build(self):
        """Test parsing version with build metadata."""
        version = SemanticVersion.parse("1.0.0+build.456")
        self.assertEqual(version.build_metadata, "build.456")

    def test_parse_full(self):
        """Test parsing full version."""
        version = SemanticVersion.parse("2.1.0-rc.1+sha.def")
        self.assertEqual(version.major, 2)
        self.assertEqual(version.minor, 1)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.prerelease, "rc.1")
        self.assertEqual(version.build_metadata, "sha.def")

    def test_parse_invalid(self):
        """Test parsing invalid version."""
        with self.assertRaises(ValueError):
            SemanticVersion.parse("invalid")

    def test_bump_major(self):
        """Test bumping major version."""
        version = SemanticVersion(major=1, minor=2, patch=3)
        new_version = version.bump(ReleaseType.MAJOR)
        self.assertEqual(new_version.major, 2)
        self.assertEqual(new_version.minor, 0)
        self.assertEqual(new_version.patch, 0)

    def test_bump_minor(self):
        """Test bumping minor version."""
        version = SemanticVersion(major=1, minor=2, patch=3)
        new_version = version.bump(ReleaseType.MINOR)
        self.assertEqual(new_version.major, 1)
        self.assertEqual(new_version.minor, 3)
        self.assertEqual(new_version.patch, 0)

    def test_bump_patch(self):
        """Test bumping patch version."""
        version = SemanticVersion(major=1, minor=2, patch=3)
        new_version = version.bump(ReleaseType.PATCH)
        self.assertEqual(new_version.major, 1)
        self.assertEqual(new_version.minor, 2)
        self.assertEqual(new_version.patch, 4)

    def test_is_stable(self):
        """Test stable version check."""
        stable = SemanticVersion(major=1, minor=0, patch=0)
        prerelease = SemanticVersion(major=1, minor=0, patch=0, prerelease="rc.1")
        self.assertTrue(stable.is_stable())
        self.assertFalse(prerelease.is_stable())

    def test_is_prerelease(self):
        """Test prerelease check."""
        stable = SemanticVersion(major=1, minor=0, patch=0)
        prerelease = SemanticVersion(major=1, minor=0, patch=0, prerelease="alpha.1")
        self.assertFalse(stable.is_prerelease())
        self.assertTrue(prerelease.is_prerelease())

    def test_comparison_lt(self):
        """Test version comparison less than."""
        v1 = SemanticVersion(major=1, minor=0, patch=0)
        v2 = SemanticVersion(major=2, minor=0, patch=0)
        self.assertTrue(v1 < v2)

    def test_comparison_prerelease(self):
        """Test prerelease version comparison."""
        stable = SemanticVersion(major=1, minor=0, patch=0)
        prerelease = SemanticVersion(major=1, minor=0, patch=0, prerelease="rc.1")
        self.assertTrue(prerelease < stable)

    def test_equality(self):
        """Test version equality."""
        v1 = SemanticVersion(major=1, minor=2, patch=3)
        v2 = SemanticVersion(major=1, minor=2, patch=3)
        self.assertEqual(v1, v2)

    def test_hash(self):
        """Test version hashing."""
        v1 = SemanticVersion(major=1, minor=0, patch=0)
        v2 = SemanticVersion(major=1, minor=0, patch=0)
        self.assertEqual(hash(v1), hash(v2))


class TestVersionManager(unittest.TestCase):
    """Tests for VersionManager."""

    def test_initial_version(self):
        """Test initial version setting."""
        manager = VersionManager("2.0.0")
        self.assertEqual(str(manager.get_current()), "2.0.0")

    def test_bump(self):
        """Test version bumping."""
        manager = VersionManager("1.0.0")
        new_version = manager.bump(ReleaseType.MINOR)
        self.assertEqual(str(new_version), "1.1.0")
        self.assertEqual(str(manager.get_current()), "1.1.0")

    def test_set_prerelease(self):
        """Test setting prerelease tag."""
        manager = VersionManager("1.0.0")
        version = manager.set_prerelease("beta.1")
        self.assertEqual(str(version), "1.0.0-beta.1")

    def test_clear_prerelease(self):
        """Test clearing prerelease tag."""
        manager = VersionManager("1.0.0")
        manager.set_prerelease("rc.1")
        version = manager.clear_prerelease()
        self.assertEqual(str(version), "1.0.0")

    def test_get_next_prerelease(self):
        """Test getting next prerelease version."""
        manager = VersionManager("1.0.0")
        version = manager.get_next_prerelease("rc")
        self.assertEqual(version.prerelease, "rc.1")

    def test_version_history(self):
        """Test version history tracking."""
        manager = VersionManager("1.0.0")
        manager.bump(ReleaseType.MINOR)
        manager.bump(ReleaseType.PATCH)
        self.assertEqual(len(manager.history), 3)


class TestChangelogEntry(unittest.TestCase):
    """Tests for ChangelogEntry."""

    def test_default_entry(self):
        """Test default entry values."""
        entry = ChangelogEntry()
        self.assertEqual(entry.change_type, ChangeType.CHANGED)
        self.assertFalse(entry.breaking)

    def test_entry_with_values(self):
        """Test entry with custom values."""
        entry = ChangelogEntry(
            change_type=ChangeType.ADDED,
            description="New feature",
            issue_refs=["#123"],
            breaking=True,
        )
        self.assertEqual(entry.change_type, ChangeType.ADDED)
        self.assertEqual(entry.description, "New feature")
        self.assertTrue(entry.breaking)


class TestChangelog(unittest.TestCase):
    """Tests for Changelog."""

    def test_add_entry(self):
        """Test adding entries."""
        changelog = Changelog()
        changelog.add_entry(ChangeType.ADDED, "New feature")
        self.assertEqual(len(changelog.entries), 1)

    def test_get_entries_by_type(self):
        """Test filtering entries by type."""
        changelog = Changelog()
        changelog.add_entry(ChangeType.ADDED, "Feature 1")
        changelog.add_entry(ChangeType.FIXED, "Bug fix")
        changelog.add_entry(ChangeType.ADDED, "Feature 2")

        added = changelog.get_entries_by_type(ChangeType.ADDED)
        self.assertEqual(len(added), 2)

    def test_has_breaking_changes(self):
        """Test breaking changes detection."""
        changelog = Changelog()
        changelog.add_entry(ChangeType.CHANGED, "Normal change")
        self.assertFalse(changelog.has_breaking_changes())

        changelog.add_entry(ChangeType.CHANGED, "Breaking", breaking=True)
        self.assertTrue(changelog.has_breaking_changes())

    def test_render_markdown(self):
        """Test Markdown rendering."""
        changelog = Changelog(
            version=SemanticVersion(major=1, minor=1, patch=0),
            summary="Test release",
        )
        changelog.add_entry(ChangeType.ADDED, "New feature")
        changelog.add_entry(ChangeType.FIXED, "Bug fix")

        markdown = changelog.render_markdown()

        self.assertIn("[1.1.0]", markdown)
        self.assertIn("Test release", markdown)
        self.assertIn("### Added", markdown)
        self.assertIn("New feature", markdown)
        self.assertIn("### Fixed", markdown)


class TestChangelogGenerator(unittest.TestCase):
    """Tests for ChangelogGenerator."""

    def setUp(self):
        self.generator = ChangelogGenerator()

    def test_create_changelog(self):
        """Test creating changelog."""
        version = SemanticVersion(major=1, minor=0, patch=0)
        changelog = self.generator.create_changelog(version, "Initial release")

        self.assertEqual(changelog.version, version)
        self.assertEqual(changelog.summary, "Initial release")

    def test_parse_conventional_commit(self):
        """Test parsing conventional commits."""
        change_type, desc, breaking, scope = self.generator.parse_conventional_commit(
            "feat(api): add new endpoint"
        )
        self.assertEqual(change_type, ChangeType.ADDED)
        self.assertEqual(desc, "add new endpoint")
        self.assertEqual(scope, "api")
        self.assertFalse(breaking)

    def test_parse_conventional_commit_breaking(self):
        """Test parsing breaking commit."""
        change_type, desc, breaking, scope = self.generator.parse_conventional_commit(
            "feat!: breaking change"
        )
        self.assertTrue(breaking)

    def test_parse_fix_commit(self):
        """Test parsing fix commit."""
        change_type, _, _, _ = self.generator.parse_conventional_commit(
            "fix: resolve issue"
        )
        self.assertEqual(change_type, ChangeType.FIXED)

    def test_add_from_commits(self):
        """Test generating changelog from commits."""
        version = SemanticVersion(major=1, minor=1, patch=0)
        commits = [
            "feat(api): add new endpoint",
            "fix: resolve bug",
            "docs: update readme",
        ]

        changelog = self.generator.add_from_commits(version, commits)

        self.assertEqual(len(changelog.entries), 3)

    def test_get_changelog(self):
        """Test retrieving changelog."""
        version = SemanticVersion(major=1, minor=0, patch=0)
        self.generator.create_changelog(version)

        retrieved = self.generator.get_changelog("1.0.0")
        self.assertIsNotNone(retrieved)

    def test_render_all(self):
        """Test rendering all changelogs."""
        self.generator.create_changelog(
            SemanticVersion(major=1, minor=0, patch=0)
        ).add_entry(ChangeType.ADDED, "Initial")

        self.generator.create_changelog(
            SemanticVersion(major=1, minor=1, patch=0)
        ).add_entry(ChangeType.ADDED, "Feature")

        markdown = self.generator.render_all()

        self.assertIn("# Changelog", markdown)
        self.assertIn("[1.0.0]", markdown)
        self.assertIn("[1.1.0]", markdown)


class TestValidationResult(unittest.TestCase):
    """Tests for ValidationResult."""

    def test_default_result(self):
        """Test default result values."""
        result = ValidationResult()
        self.assertEqual(result.gate, ValidationGate.UNIT_TESTS)
        self.assertFalse(result.passed)

    def test_result_with_values(self):
        """Test result with custom values."""
        result = ValidationResult(
            gate=ValidationGate.SECURITY_SCAN,
            passed=True,
            message="No vulnerabilities found",
        )
        self.assertEqual(result.gate, ValidationGate.SECURITY_SCAN)
        self.assertTrue(result.passed)


class TestReleaseValidator(unittest.TestCase):
    """Tests for ReleaseValidator."""

    def setUp(self):
        self.validator = ReleaseValidator()
        self.release = Release()

    def test_register_gate(self):
        """Test registering validation gate."""

        def check() -> tuple[bool, str, dict]:
            return True, "Passed", {}

        self.validator.register_gate(ValidationGate.UNIT_TESTS, check)
        self.assertIn(ValidationGate.UNIT_TESTS, self.validator.gates)

    def test_validate_all_pass(self):
        """Test validation with all gates passing."""

        def pass_check() -> tuple[bool, str, dict]:
            return True, "Passed", {}

        self.validator.register_gate(ValidationGate.UNIT_TESTS, pass_check)
        self.validator.register_gate(ValidationGate.SECURITY_SCAN, pass_check)
        self.validator.register_gate(ValidationGate.CODE_COVERAGE, pass_check)

        results = self.validator.validate(self.release)

        self.assertEqual(len(results), 3)
        self.assertEqual(self.release.status, ReleaseStatus.VALIDATED)

    def test_validate_with_failure(self):
        """Test validation with failing gate."""

        def pass_check() -> tuple[bool, str, dict]:
            return True, "Passed", {}

        def fail_check() -> tuple[bool, str, dict]:
            return False, "Failed", {}

        self.validator.register_gate(ValidationGate.UNIT_TESTS, fail_check)
        self.validator.register_gate(ValidationGate.SECURITY_SCAN, pass_check)

        results = self.validator.validate(self.release)

        self.assertEqual(self.release.status, ReleaseStatus.FAILED)

    def test_validate_exception_handling(self):
        """Test validation with exception."""

        def error_check() -> tuple[bool, str, dict]:
            raise RuntimeError("Check error")

        self.validator.register_gate(ValidationGate.UNIT_TESTS, error_check)

        results = self.validator.validate(self.release)

        self.assertFalse(results[0].passed)
        self.assertIn("error", results[0].message)

    def test_get_validation_summary(self):
        """Test getting validation summary."""

        def check() -> tuple[bool, str, dict]:
            return True, "OK", {}

        self.validator.register_gate(ValidationGate.UNIT_TESTS, check)
        results = self.validator.validate(self.release)

        summary = self.validator.get_validation_summary(results)

        self.assertEqual(summary["total_gates"], 1)
        self.assertEqual(summary["passed"], 1)
        self.assertTrue(summary["all_required_passed"])


class TestReleaseArtifact(unittest.TestCase):
    """Tests for ReleaseArtifact."""

    def test_default_artifact(self):
        """Test default artifact values."""
        artifact = ReleaseArtifact()
        self.assertIsNotNone(artifact.artifact_id)
        self.assertEqual(artifact.size_bytes, 0)

    def test_compute_checksum(self):
        """Test computing checksum."""
        artifact = ReleaseArtifact()
        content = b"test content"
        checksum = artifact.compute_checksum(content)

        self.assertEqual(len(checksum), 64)  # SHA-256
        self.assertEqual(artifact.size_bytes, len(content))


class TestArtifactBuilder(unittest.TestCase):
    """Tests for ArtifactBuilder."""

    def setUp(self):
        self.builder = ArtifactBuilder()
        self.release = Release()

    def test_register_builder(self):
        """Test registering artifact builder."""

        def build_wheel(r: Release) -> ReleaseArtifact:
            return ReleaseArtifact(name="test.whl", artifact_type="wheel")

        self.builder.register_builder("wheel", build_wheel)
        self.assertIn("wheel", self.builder.builders)

    def test_build(self):
        """Test building artifacts."""

        def build_wheel(r: Release) -> ReleaseArtifact:
            return ReleaseArtifact(name="test.whl", artifact_type="wheel")

        self.builder.register_builder("wheel", build_wheel)

        artifacts = self.builder.build(self.release)

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(self.release.status, ReleaseStatus.BUILT)

    def test_build_specific_types(self):
        """Test building specific artifact types."""

        def build_wheel(r: Release) -> ReleaseArtifact:
            return ReleaseArtifact(name="test.whl", artifact_type="wheel")

        def build_docker(r: Release) -> ReleaseArtifact:
            return ReleaseArtifact(name="image", artifact_type="docker")

        self.builder.register_builder("wheel", build_wheel)
        self.builder.register_builder("docker", build_docker)

        artifacts = self.builder.build(self.release, ["wheel"])

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].artifact_type, "wheel")

    def test_create_simple_artifact(self):
        """Test creating simple artifact."""
        artifact = self.builder.create_simple_artifact(
            name="test.txt",
            artifact_type="text",
            content=b"hello world",
        )

        self.assertEqual(artifact.name, "test.txt")
        self.assertEqual(artifact.size_bytes, 11)
        self.assertIsNotNone(artifact.checksum_sha256)


class TestDistributionManager(unittest.TestCase):
    """Tests for DistributionManager."""

    def setUp(self):
        self.manager = DistributionManager()
        self.release = Release()

    def test_register_publisher(self):
        """Test registering publisher."""

        def publish(r: Release) -> tuple[bool, str]:
            return True, "Published"

        self.manager.register_publisher(DistributionChannel.PYPI, publish)
        self.assertIn(DistributionChannel.PYPI, self.manager.publishers)

    def test_publish_success(self):
        """Test successful publishing."""

        def publish(r: Release) -> tuple[bool, str]:
            return True, "Published to PyPI"

        self.manager.register_publisher(DistributionChannel.PYPI, publish)

        results = self.manager.publish(self.release)

        self.assertTrue(results[DistributionChannel.PYPI][0])
        self.assertEqual(self.release.status, ReleaseStatus.PUBLISHED)

    def test_publish_failure(self):
        """Test failed publishing."""

        def publish(r: Release) -> tuple[bool, str]:
            return False, "Upload failed"

        self.manager.register_publisher(DistributionChannel.PYPI, publish)

        results = self.manager.publish(self.release)

        self.assertFalse(results[DistributionChannel.PYPI][0])
        self.assertEqual(self.release.status, ReleaseStatus.FAILED)

    def test_publish_exception(self):
        """Test publishing with exception."""

        def publish(r: Release) -> tuple[bool, str]:
            raise RuntimeError("Network error")

        self.manager.register_publisher(DistributionChannel.PYPI, publish)

        results = self.manager.publish(self.release)

        self.assertFalse(results[DistributionChannel.PYPI][0])

    def test_publish_no_publisher(self):
        """Test publishing to unregistered channel."""
        results = self.manager.publish(self.release, [DistributionChannel.NPM])

        self.assertFalse(results[DistributionChannel.NPM][0])


class TestRelease(unittest.TestCase):
    """Tests for Release dataclass."""

    def test_default_release(self):
        """Test default release values."""
        release = Release()
        self.assertIsNotNone(release.release_id)
        self.assertEqual(release.status, ReleaseStatus.DRAFT)
        self.assertEqual(release.release_type, ReleaseType.MINOR)

    def test_release_with_values(self):
        """Test release with custom values."""
        release = Release(
            release_type=ReleaseType.MAJOR,
            version=SemanticVersion(major=2, minor=0, patch=0),
            created_by="Developer",
        )
        self.assertEqual(release.release_type, ReleaseType.MAJOR)
        self.assertEqual(str(release.version), "2.0.0")


class TestReleaseManager(unittest.TestCase):
    """Tests for ReleaseManager."""

    def setUp(self):
        self.manager = ReleaseManager(
            product_name="TestProduct",
            current_version="1.0.0",
        )

    def test_create_release(self):
        """Test creating release."""
        release = self.manager.create_release(
            release_type=ReleaseType.MINOR,
            summary="New features",
            created_by="Tester",
        )

        self.assertEqual(str(release.version), "1.1.0")
        self.assertEqual(release.status, ReleaseStatus.DRAFT)

    def test_prepare_ga_release(self):
        """Test preparing GA release."""
        release = self.manager.prepare_ga_release(
            summary="General Availability",
            created_by="Release Manager",
        )

        self.assertTrue(release.version.is_stable())
        self.assertIn("General Availability", release.notes)

    def test_validate_release(self):
        """Test validating release."""

        def check() -> tuple[bool, str, dict]:
            return True, "OK", {}

        self.manager.validator.register_gate(ValidationGate.UNIT_TESTS, check)
        self.manager.validator.register_gate(ValidationGate.SECURITY_SCAN, check)
        self.manager.validator.register_gate(ValidationGate.CODE_COVERAGE, check)

        release = self.manager.create_release(ReleaseType.PATCH)
        passed = self.manager.validate_release(release)

        self.assertTrue(passed)

    def test_build_release(self):
        """Test building release."""

        def build(r: Release) -> ReleaseArtifact:
            return ReleaseArtifact(name="artifact", artifact_type="test")

        self.manager.artifact_builder.register_builder("test", build)

        release = self.manager.create_release(ReleaseType.PATCH)
        artifacts = self.manager.build_release(release)

        self.assertEqual(len(artifacts), 1)

    def test_get_release(self):
        """Test retrieving release."""
        release = self.manager.create_release(ReleaseType.MINOR)
        version = str(release.version)

        retrieved = self.manager.get_release(version)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.release_id, release.release_id)

    def test_get_release_history(self):
        """Test getting release history."""
        self.manager.create_release(ReleaseType.MINOR)
        self.manager.create_release(ReleaseType.PATCH)

        history = self.manager.get_release_history()

        self.assertEqual(len(history), 2)

    def test_get_current_version(self):
        """Test getting current version."""
        version = self.manager.get_current_version()
        self.assertEqual(version, "1.0.0")

        self.manager.create_release(ReleaseType.MINOR)
        version = self.manager.get_current_version()
        self.assertEqual(version, "1.1.0")

    def test_execute_full_release_success(self):
        """Test executing full release workflow."""

        def check() -> tuple[bool, str, dict]:
            return True, "OK", {}

        def build(r: Release) -> ReleaseArtifact:
            return ReleaseArtifact(name="artifact", artifact_type="test")

        self.manager.validator.register_gate(ValidationGate.UNIT_TESTS, check)
        self.manager.validator.register_gate(ValidationGate.SECURITY_SCAN, check)
        self.manager.validator.register_gate(ValidationGate.CODE_COVERAGE, check)
        self.manager.artifact_builder.register_builder("test", build)

        result = self.manager.execute_full_release(
            release_type=ReleaseType.MINOR,
            summary="Test release",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["version"], "1.1.0")
        self.assertEqual(result["artifacts"], 1)

    def test_execute_full_release_validation_failure(self):
        """Test release workflow with validation failure."""

        def fail_check() -> tuple[bool, str, dict]:
            return False, "Failed", {}

        self.manager.validator.register_gate(ValidationGate.UNIT_TESTS, fail_check)

        result = self.manager.execute_full_release(ReleaseType.MINOR)

        self.assertFalse(result["success"])
        self.assertIn("Validation failed", result["error"])


class TestChangeType(unittest.TestCase):
    """Tests for ChangeType enum."""

    def test_change_type_values(self):
        """Test change type values."""
        self.assertEqual(ChangeType.ADDED.value, "added")
        self.assertEqual(ChangeType.FIXED.value, "fixed")
        self.assertEqual(ChangeType.SECURITY.value, "security")


class TestReleaseType(unittest.TestCase):
    """Tests for ReleaseType enum."""

    def test_release_type_values(self):
        """Test release type values."""
        self.assertEqual(ReleaseType.MAJOR.value, "major")
        self.assertEqual(ReleaseType.MINOR.value, "minor")
        self.assertEqual(ReleaseType.PATCH.value, "patch")
        self.assertEqual(ReleaseType.HOTFIX.value, "hotfix")


class TestReleaseStatus(unittest.TestCase):
    """Tests for ReleaseStatus enum."""

    def test_release_status_values(self):
        """Test release status values."""
        self.assertEqual(ReleaseStatus.DRAFT.value, "draft")
        self.assertEqual(ReleaseStatus.PUBLISHED.value, "published")
        self.assertEqual(ReleaseStatus.ROLLED_BACK.value, "rolled_back")


class TestDistributionChannel(unittest.TestCase):
    """Tests for DistributionChannel enum."""

    def test_channel_values(self):
        """Test distribution channel values."""
        self.assertEqual(DistributionChannel.PYPI.value, "pypi")
        self.assertEqual(DistributionChannel.DOCKER_HUB.value, "docker_hub")
        self.assertEqual(DistributionChannel.GITHUB.value, "github")


if __name__ == "__main__":
    unittest.main()
