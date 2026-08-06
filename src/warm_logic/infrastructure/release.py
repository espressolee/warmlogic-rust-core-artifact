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
"""
[Q4 2026] Release Management Infrastructure

Provides comprehensive release management:
- Semantic versioning (SemVer 2.0)
- Changelog generation
- Release validation gates
- Release artifact packaging
- Distribution channel management
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class ReleaseType(Enum):
    """Types of releases."""

    MAJOR = "major"  # Breaking changes
    MINOR = "minor"  # New features, backward compatible
    PATCH = "patch"  # Bug fixes
    PRERELEASE = "prerelease"  # Alpha, beta, RC
    HOTFIX = "hotfix"  # Emergency fixes


class ReleaseStatus(Enum):
    """Release workflow status."""

    DRAFT = "draft"
    VALIDATING = "validating"
    VALIDATED = "validated"
    BUILDING = "building"
    BUILT = "built"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ChangeType(Enum):
    """Types of changes for changelog."""

    ADDED = "added"
    CHANGED = "changed"
    DEPRECATED = "deprecated"
    REMOVED = "removed"
    FIXED = "fixed"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"


class ValidationGate(Enum):
    """Release validation gates."""

    UNIT_TESTS = "unit_tests"
    INTEGRATION_TESTS = "integration_tests"
    SECURITY_SCAN = "security_scan"
    PERFORMANCE_BENCHMARK = "performance_benchmark"
    CODE_COVERAGE = "code_coverage"
    DOCUMENTATION = "documentation"
    TRL_CERTIFICATION = "trl_certification"
    COMPLIANCE_CHECK = "compliance_check"
    DEPENDENCY_AUDIT = "dependency_audit"
    LICENSE_CHECK = "license_check"


class DistributionChannel(Enum):
    """Distribution channels for releases."""

    PYPI = "pypi"
    GITHUB = "github"
    DOCKER_HUB = "docker_hub"
    NPM = "npm"
    INTERNAL = "internal"
    ENTERPRISE = "enterprise"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SemanticVersion:
    """Semantic Version representation (SemVer 2.0)."""

    major: int = 1
    minor: int = 0
    patch: int = 0
    prerelease: str = ""  # e.g., "alpha.1", "beta.2", "rc.1"
    build_metadata: str = ""  # e.g., "build.123"

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        return version

    def __lt__(self, other: SemanticVersion) -> bool:
        if (self.major, self.minor, self.patch) != (
            other.major,
            other.minor,
            other.patch,
        ):
            return (self.major, self.minor, self.patch) < (
                other.major,
                other.minor,
                other.patch,
            )
        # Pre-release versions have lower precedence
        if self.prerelease and not other.prerelease:
            return True
        if not self.prerelease and other.prerelease:
            return False
        return self.prerelease < other.prerelease

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return False
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
        )

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.prerelease))

    @classmethod
    def parse(cls, version_string: str) -> SemanticVersion:
        """Parse a version string into SemanticVersion."""
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?(?:\+([a-zA-Z0-9.]+))?$"
        match = re.match(pattern, version_string)
        if not match:
            raise ValueError(f"Invalid version string: {version_string}")

        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4) or "",
            build_metadata=match.group(5) or "",
        )

    def bump(self, release_type: ReleaseType) -> SemanticVersion:
        """Create a new version with bumped component."""
        if release_type == ReleaseType.MAJOR:
            return SemanticVersion(major=self.major + 1, minor=0, patch=0)
        elif release_type == ReleaseType.MINOR:
            return SemanticVersion(major=self.major, minor=self.minor + 1, patch=0)
        elif release_type in (ReleaseType.PATCH, ReleaseType.HOTFIX):
            return SemanticVersion(
                major=self.major, minor=self.minor, patch=self.patch + 1
            )
        else:
            return SemanticVersion(
                major=self.major,
                minor=self.minor,
                patch=self.patch,
                prerelease=self.prerelease,
            )

    def is_stable(self) -> bool:
        """Check if version is stable (no prerelease tag)."""
        return not self.prerelease

    def is_prerelease(self) -> bool:
        """Check if version is a prerelease."""
        return bool(self.prerelease)


@dataclass
class ChangelogEntry:
    """Single entry in the changelog."""

    change_type: ChangeType = ChangeType.CHANGED
    description: str = ""
    issue_refs: list[str] = field(default_factory=list)  # e.g., ["#123", "#456"]
    pr_refs: list[str] = field(default_factory=list)
    author: str = ""
    breaking: bool = False
    scope: str = ""  # e.g., "api", "cli", "core"


@dataclass
class Changelog:
    """Changelog for a release."""

    version: SemanticVersion = field(default_factory=SemanticVersion)
    release_date: datetime = field(default_factory=datetime.utcnow)
    entries: list[ChangelogEntry] = field(default_factory=list)
    summary: str = ""
    contributors: list[str] = field(default_factory=list)

    def add_entry(
        self,
        change_type: ChangeType,
        description: str,
        **kwargs: Any,
    ) -> ChangelogEntry:
        """Add an entry to the changelog."""
        entry = ChangelogEntry(
            change_type=change_type,
            description=description,
            **kwargs,
        )
        self.entries.append(entry)
        return entry

    def get_entries_by_type(self, change_type: ChangeType) -> list[ChangelogEntry]:
        """Get entries of a specific type."""
        return [e for e in self.entries if e.change_type == change_type]

    def has_breaking_changes(self) -> bool:
        """Check if changelog has breaking changes."""
        return any(e.breaking for e in self.entries)

    def render_markdown(self) -> str:
        """Render changelog as Markdown."""
        lines = [
            f"## [{self.version}] - {self.release_date.strftime('%Y-%m-%d')}",
            "",
        ]

        if self.summary:
            lines.extend([self.summary, ""])

        # Group by change type
        for change_type in ChangeType:
            entries = self.get_entries_by_type(change_type)
            if entries:
                lines.append(f"### {change_type.value.title()}")
                for entry in entries:
                    prefix = "**BREAKING:** " if entry.breaking else ""
                    scope = f"**{entry.scope}:** " if entry.scope else ""
                    refs = ""
                    if entry.issue_refs or entry.pr_refs:
                        all_refs = entry.issue_refs + entry.pr_refs
                        refs = f" ({', '.join(all_refs)})"
                    lines.append(f"- {prefix}{scope}{entry.description}{refs}")
                lines.append("")

        if self.contributors:
            lines.extend(["### Contributors", ""])
            for contributor in self.contributors:
                lines.append(f"- {contributor}")
            lines.append("")

        return "\n".join(lines)


@dataclass
class ValidationResult:
    """Result of a validation gate check."""

    gate: ValidationGate = ValidationGate.UNIT_TESTS
    passed: bool = False
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReleaseArtifact:
    """Release artifact metadata."""

    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    artifact_type: str = ""  # e.g., "wheel", "sdist", "docker"
    path: str = ""
    size_bytes: int = 0
    checksum_sha256: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_checksum(self, content: bytes) -> str:
        """Compute and store checksum."""
        self.checksum_sha256 = hashlib.sha256(content).hexdigest()
        self.size_bytes = len(content)
        return self.checksum_sha256


@dataclass
class Release:
    """Release record."""

    release_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: SemanticVersion = field(default_factory=SemanticVersion)
    release_type: ReleaseType = ReleaseType.MINOR
    status: ReleaseStatus = ReleaseStatus.DRAFT
    changelog: Changelog = field(default_factory=Changelog)
    artifacts: list[ReleaseArtifact] = field(default_factory=list)
    validation_results: list[ValidationResult] = field(default_factory=list)
    channels: list[DistributionChannel] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    published_at: datetime | None = None
    created_by: str = ""
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Version Manager
# =============================================================================


class VersionManager:
    """
    Manages version lifecycle.

    Tracks versions and determines next version based on changes.
    """

    def __init__(self, current_version: str = "1.0.0"):
        self.current = SemanticVersion.parse(current_version)
        self.history: list[SemanticVersion] = [self.current]

    def get_current(self) -> SemanticVersion:
        """Get current version."""
        return self.current

    def bump(self, release_type: ReleaseType) -> SemanticVersion:
        """Bump version and return new version."""
        new_version = self.current.bump(release_type)
        self.current = new_version
        self.history.append(new_version)
        return new_version

    def set_prerelease(self, tag: str) -> SemanticVersion:
        """Set prerelease tag on current version."""
        self.current = SemanticVersion(
            major=self.current.major,
            minor=self.current.minor,
            patch=self.current.patch,
            prerelease=tag,
        )
        return self.current

    def clear_prerelease(self) -> SemanticVersion:
        """Clear prerelease tag for stable release."""
        self.current = SemanticVersion(
            major=self.current.major,
            minor=self.current.minor,
            patch=self.current.patch,
        )
        return self.current

    def get_next_prerelease(self, base_tag: str = "rc") -> SemanticVersion:
        """Get next prerelease version."""
        # Find highest existing prerelease number
        current_num = 0
        for v in self.history:
            if v.prerelease.startswith(base_tag):
                try:
                    num = int(v.prerelease.split(".")[-1])
                    current_num = max(current_num, num)
                except (ValueError, IndexError):
                    pass

        new_tag = f"{base_tag}.{current_num + 1}"
        return SemanticVersion(
            major=self.current.major,
            minor=self.current.minor,
            patch=self.current.patch,
            prerelease=new_tag,
        )


# =============================================================================
# Changelog Generator
# =============================================================================


class ChangelogGenerator:
    """
    Generates changelogs from commit history or manual entries.

    Supports conventional commits format.
    """

    def __init__(self) -> None:
        self.changelogs: dict[str, Changelog] = {}

    def create_changelog(
        self,
        version: SemanticVersion,
        summary: str = "",
    ) -> Changelog:
        """Create a new changelog for a version."""
        changelog = Changelog(version=version, summary=summary)
        self.changelogs[str(version)] = changelog
        return changelog

    def parse_conventional_commit(
        self,
        message: str,
    ) -> tuple[ChangeType, str, bool, str]:
        """
        Parse a conventional commit message.

        Format: type(scope)!: description

        Returns:
            (change_type, description, is_breaking, scope)
        """
        # Pattern: type(scope)!: description
        pattern = r"^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.+)$"
        match = re.match(pattern, message.strip())

        if not match:
            return ChangeType.CHANGED, message, False, ""

        commit_type = match.group(1).lower()
        scope = match.group(2) or ""
        is_breaking = bool(match.group(3))
        description = match.group(4)

        # Map commit types to change types
        type_mapping = {
            "feat": ChangeType.ADDED,
            "fix": ChangeType.FIXED,
            "docs": ChangeType.DOCUMENTATION,
            "perf": ChangeType.PERFORMANCE,
            "security": ChangeType.SECURITY,
            "deprecate": ChangeType.DEPRECATED,
            "remove": ChangeType.REMOVED,
            "chore": ChangeType.CHANGED,
            "refactor": ChangeType.CHANGED,
            "style": ChangeType.CHANGED,
            "test": ChangeType.CHANGED,
            "ci": ChangeType.CHANGED,
        }

        change_type = type_mapping.get(commit_type, ChangeType.CHANGED)
        return change_type, description, is_breaking, scope

    def add_from_commits(
        self,
        version: SemanticVersion,
        commits: list[str],
    ) -> Changelog:
        """Generate changelog from commit messages."""
        changelog = self.create_changelog(version)

        for commit in commits:
            change_type, description, breaking, scope = self.parse_conventional_commit(
                commit
            )
            changelog.add_entry(
                change_type=change_type,
                description=description,
                breaking=breaking,
                scope=scope,
            )

        return changelog

    def get_changelog(self, version: str) -> Changelog | None:
        """Get changelog for a specific version."""
        return self.changelogs.get(version)

    def render_all(self) -> str:
        """Render all changelogs as Markdown."""
        lines = ["# Changelog", "", "All notable changes to this project.", ""]

        # Sort versions descending
        sorted_versions = sorted(
            self.changelogs.keys(),
            key=lambda v: SemanticVersion.parse(v),
            reverse=True,
        )

        for version in sorted_versions:
            changelog = self.changelogs[version]
            lines.append(changelog.render_markdown())

        return "\n".join(lines)


# =============================================================================
# Release Validator
# =============================================================================


class ReleaseValidator:
    """
    Validates releases against quality gates.

    Runs automated checks before release.
    """

    def __init__(self) -> None:
        self.gates: dict[ValidationGate, Callable[[], tuple[bool, str, dict]]] = {}
        self.required_gates: set[ValidationGate] = {
            ValidationGate.UNIT_TESTS,
            ValidationGate.SECURITY_SCAN,
            ValidationGate.CODE_COVERAGE,
        }

    def register_gate(
        self,
        gate: ValidationGate,
        check_func: Callable[[], tuple[bool, str, dict]],
        required: bool = True,
    ) -> None:
        """
        Register a validation gate.

        Args:
            gate: The validation gate type
            check_func: Function returning (passed, message, details)
            required: Whether this gate is required for release
        """
        self.gates[gate] = check_func
        if required:
            self.required_gates.add(gate)

    def validate(self, release: Release) -> list[ValidationResult]:
        """
        Run all validation gates for a release.

        Returns:
            List of validation results.
        """
        results = []
        release.status = ReleaseStatus.VALIDATING

        for gate, check_func in self.gates.items():
            start_time = datetime.utcnow()

            try:
                passed, message, details = check_func()
            except Exception as e:
                passed = False
                message = f"Gate check failed with error: {e}"
                details = {"error": str(e)}

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = ValidationResult(
                gate=gate,
                passed=passed,
                message=message,
                details=details,
                duration_seconds=duration,
            )
            results.append(result)

        release.validation_results = results

        # Check if all required gates passed
        required_passed = all(
            r.passed for r in results if r.gate in self.required_gates
        )

        release.status = (
            ReleaseStatus.VALIDATED if required_passed else ReleaseStatus.FAILED
        )

        return results

    def get_validation_summary(
        self,
        results: list[ValidationResult],
    ) -> dict[str, Any]:
        """Get summary of validation results."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        required = [r for r in results if r.gate in self.required_gates]
        required_passed = sum(1 for r in required if r.passed)

        return {
            "total_gates": total,
            "passed": passed,
            "failed": failed,
            "required_passed": required_passed,
            "required_total": len(required),
            "all_required_passed": required_passed == len(required),
            "total_duration_seconds": sum(r.duration_seconds for r in results),
            "details": [
                {
                    "gate": r.gate.value,
                    "passed": r.passed,
                    "message": r.message,
                    "duration": r.duration_seconds,
                }
                for r in results
            ],
        }


# =============================================================================
# Artifact Builder
# =============================================================================


class ArtifactBuilder:
    """
    Builds release artifacts.

    Supports multiple artifact types.
    """

    def __init__(self) -> None:
        self.builders: dict[str, Callable[[Release], ReleaseArtifact | None]] = {}

    def register_builder(
        self,
        artifact_type: str,
        builder_func: Callable[[Release], ReleaseArtifact | None],
    ) -> None:
        """Register an artifact builder."""
        self.builders[artifact_type] = builder_func

    def build(
        self,
        release: Release,
        artifact_types: list[str] | None = None,
    ) -> list[ReleaseArtifact]:
        """
        Build artifacts for a release.

        Args:
            release: The release to build
            artifact_types: Types to build (or all if None)

        Returns:
            List of built artifacts.
        """
        release.status = ReleaseStatus.BUILDING
        artifacts = []

        types_to_build = artifact_types or list(self.builders.keys())

        for artifact_type in types_to_build:
            if artifact_type not in self.builders:
                continue

            try:
                artifact = self.builders[artifact_type](release)
                if artifact:
                    artifacts.append(artifact)
            except Exception as e:
                logger.error(f"Failed to build {artifact_type}: {e}")

        release.artifacts = artifacts
        release.status = ReleaseStatus.BUILT if artifacts else ReleaseStatus.FAILED

        return artifacts

    def create_simple_artifact(
        self,
        name: str,
        artifact_type: str,
        content: bytes,
        path: str = "",
    ) -> ReleaseArtifact:
        """Create a simple artifact from content."""
        artifact = ReleaseArtifact(
            name=name,
            artifact_type=artifact_type,
            path=path,
        )
        artifact.compute_checksum(content)
        return artifact


# =============================================================================
# Distribution Manager
# =============================================================================


class DistributionManager:
    """
    Manages release distribution to channels.

    Handles publishing to various repositories.
    """

    def __init__(self) -> None:
        self.publishers: dict[
            DistributionChannel, Callable[[Release], tuple[bool, str]]
        ] = {}

    def register_publisher(
        self,
        channel: DistributionChannel,
        publish_func: Callable[[Release], tuple[bool, str]],
    ) -> None:
        """Register a publisher for a channel."""
        self.publishers[channel] = publish_func

    def publish(
        self,
        release: Release,
        channels: list[DistributionChannel] | None = None,
    ) -> dict[DistributionChannel, tuple[bool, str]]:
        """
        Publish release to distribution channels.

        Args:
            release: The release to publish
            channels: Channels to publish to (or all registered if None)

        Returns:
            Dict of channel -> (success, message)
        """
        release.status = ReleaseStatus.PUBLISHING
        results = {}

        channels_to_use = channels or list(self.publishers.keys())
        release.channels = channels_to_use

        all_success = True
        for channel in channels_to_use:
            if channel not in self.publishers:
                results[channel] = (False, "No publisher registered")
                all_success = False
                continue

            try:
                success, message = self.publishers[channel](release)
                results[channel] = (success, message)
                if not success:
                    all_success = False
            except Exception as e:
                results[channel] = (False, str(e))
                all_success = False

        if all_success:
            release.status = ReleaseStatus.PUBLISHED
            release.published_at = datetime.utcnow()
        else:
            release.status = ReleaseStatus.FAILED

        return results


# =============================================================================
# Release Manager
# =============================================================================


class ReleaseManager:
    """
    Central release management system.

    Orchestrates the entire release process.
    """

    def __init__(
        self,
        product_name: str = "WarmLogic",
        current_version: str = "1.0.0",
    ):
        self.product_name = product_name
        self.version_manager = VersionManager(current_version)
        self.changelog_generator = ChangelogGenerator()
        self.validator = ReleaseValidator()
        self.artifact_builder = ArtifactBuilder()
        self.distribution = DistributionManager()
        self.releases: dict[str, Release] = {}

    def create_release(
        self,
        release_type: ReleaseType,
        summary: str = "",
        created_by: str = "",
    ) -> Release:
        """
        Create a new release.

        Args:
            release_type: Type of release
            summary: Release summary
            created_by: Creator name

        Returns:
            New Release object
        """
        # Bump version
        new_version = self.version_manager.bump(release_type)

        # Create changelog
        changelog = self.changelog_generator.create_changelog(
            version=new_version,
            summary=summary,
        )

        release = Release(
            version=new_version,
            release_type=release_type,
            changelog=changelog,
            created_by=created_by,
        )

        self.releases[str(new_version)] = release

        logger.info(f"Created {release_type.value} release: v{new_version}")
        return release

    def prepare_ga_release(
        self,
        summary: str = "",
        created_by: str = "",
    ) -> Release:
        """
        Prepare a GA (General Availability) release.

        Clears any prerelease tags and creates stable release.
        """
        # Clear any prerelease tag
        self.version_manager.clear_prerelease()
        version = self.version_manager.get_current()

        changelog = self.changelog_generator.create_changelog(
            version=version,
            summary=summary or f"{self.product_name} v{version} - General Availability",
        )

        release = Release(
            version=version,
            release_type=ReleaseType.MAJOR,
            changelog=changelog,
            created_by=created_by,
            notes="General Availability Release",
        )

        self.releases[str(version)] = release

        logger.info(f"Prepared GA release: v{version}")
        return release

    def validate_release(self, release: Release) -> bool:
        """Validate a release against all gates."""
        results = self.validator.validate(release)
        summary = self.validator.get_validation_summary(results)
        return bool(summary["all_required_passed"])

    def build_release(
        self,
        release: Release,
        artifact_types: list[str] | None = None,
    ) -> list[ReleaseArtifact]:
        """Build release artifacts."""
        return self.artifact_builder.build(release, artifact_types)

    def publish_release(
        self,
        release: Release,
        channels: list[DistributionChannel] | None = None,
    ) -> dict[DistributionChannel, tuple[bool, str]]:
        """Publish release to distribution channels."""
        return self.distribution.publish(release, channels)

    def execute_full_release(
        self,
        release_type: ReleaseType,
        summary: str = "",
        created_by: str = "",
        channels: list[DistributionChannel] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a full release workflow.

        Steps:
        1. Create release
        2. Validate
        3. Build artifacts
        4. Publish

        Returns:
            Release execution result.
        """
        # Create
        release = self.create_release(release_type, summary, created_by)

        # Validate
        validation_passed = self.validate_release(release)
        if not validation_passed:
            return {
                "success": False,
                "release_id": release.release_id,
                "version": str(release.version),
                "status": release.status.value,
                "error": "Validation failed",
                "validation": self.validator.get_validation_summary(
                    release.validation_results
                ),
            }

        # Build
        artifacts = self.build_release(release)
        if not artifacts:
            return {
                "success": False,
                "release_id": release.release_id,
                "version": str(release.version),
                "status": release.status.value,
                "error": "No artifacts built",
            }

        # Publish
        if channels:
            publish_results = self.publish_release(release, channels)
            all_published = all(r[0] for r in publish_results.values())

            if not all_published:
                return {
                    "success": False,
                    "release_id": release.release_id,
                    "version": str(release.version),
                    "status": release.status.value,
                    "error": "Publishing failed",
                    "publish_results": {
                        k.value: {"success": v[0], "message": v[1]}
                        for k, v in publish_results.items()
                    },
                }

        return {
            "success": True,
            "release_id": release.release_id,
            "version": str(release.version),
            "status": release.status.value,
            "artifacts": len(release.artifacts),
            "channels": [c.value for c in release.channels],
        }

    def get_release(self, version: str) -> Release | None:
        """Get a release by version."""
        return self.releases.get(version)

    def get_release_history(self) -> list[dict[str, Any]]:
        """Get release history summary."""
        return [
            {
                "version": str(r.version),
                "type": r.release_type.value,
                "status": r.status.value,
                "created_at": r.created_at.isoformat(),
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in sorted(
                self.releases.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )
        ]

    def get_current_version(self) -> str:
        """Get current version string."""
        return str(self.version_manager.get_current())
