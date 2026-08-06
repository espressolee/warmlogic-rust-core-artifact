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
[Q3 2026] Compliance Documentation Package

Provides unified compliance documentation generation:
- Multi-framework compliance reports
- Audit trail documentation
- Evidence collection and packaging
- Regulatory submission preparation

Supported frameworks:
- GDPR (EU General Data Protection Regulation)
- SOC 2 Type I/II (Service Organization Control)
- HIPAA (Health Insurance Portability and Accountability Act)
- EU AI Act (Regulation (EU) 2024/1689)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class ComplianceFramework(Enum):
    """Supported compliance frameworks"""

    GDPR = "gdpr"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    EU_AI_ACT = "eu_ai_act"


class DocumentType(Enum):
    """Types of compliance documents"""

    POLICY = "policy"
    PROCEDURE = "procedure"
    EVIDENCE = "evidence"
    AUDIT_REPORT = "audit_report"
    RISK_ASSESSMENT = "risk_assessment"
    TRAINING_RECORD = "training_record"
    INCIDENT_REPORT = "incident_report"
    COMPLIANCE_MATRIX = "compliance_matrix"


class AuditStatus(Enum):
    """Audit status types"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ComplianceDocument:
    """Represents a compliance document"""

    doc_id: str = ""
    title: str = ""
    document_type: DocumentType = DocumentType.POLICY
    framework: ComplianceFramework = ComplianceFramework.GDPR
    version: str = "1.0.0"
    created_date: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    author: str = ""
    approver: str = ""
    content_hash: str = ""
    file_path: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    """Represents an evidence item for compliance"""

    evidence_id: str = ""
    title: str = ""
    description: str = ""
    framework: ComplianceFramework = ComplianceFramework.GDPR
    control_id: str = ""  # Reference to specific control
    collected_date: datetime = field(default_factory=datetime.utcnow)
    collector: str = ""
    evidence_type: str = ""  # screenshot, log, report, etc.
    file_path: str = ""
    content_hash: str = ""
    retention_period_days: int = 365 * 7  # 7 years default


@dataclass
class AuditTrailEntry:
    """Represents an entry in the audit trail"""

    entry_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    action: str = ""
    actor: str = ""
    resource_type: str = ""
    resource_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    framework: ComplianceFramework | None = None


@dataclass
class ComplianceReport:
    """Comprehensive compliance report"""

    report_id: str = ""
    title: str = ""
    generated_date: datetime = field(default_factory=datetime.utcnow)
    period_start: datetime | None = None
    period_end: datetime | None = None
    frameworks: list[ComplianceFramework] = field(default_factory=list)
    overall_score: float = 0.0
    status: AuditStatus = AuditStatus.NOT_STARTED
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    framework_scores: dict[str, float] = field(default_factory=dict)
    executive_summary: str = ""


# =============================================================================
# Document Registry
# =============================================================================


class DocumentRegistry:
    """
    Registry for compliance documents.

    Manages document lifecycle, versioning, and retrieval.
    """

    def __init__(self) -> None:
        self.documents: dict[str, ComplianceDocument] = {}
        self._version_counter: dict[str, int] = {}

    def register_document(
        self,
        title: str,
        document_type: DocumentType,
        framework: ComplianceFramework,
        author: str,
        content: str | bytes = "",
        file_path: str = "",
        tags: list[str] | None = None,
    ) -> ComplianceDocument:
        """
        Register a compliance document.

        Args:
            title: Document title
            document_type: Type of document
            framework: Compliance framework
            author: Document author
            content: Document content (for hash calculation)
            file_path: Path to document file
            tags: Optional tags

        Returns:
            ComplianceDocument
        """
        import uuid

        doc_id = str(uuid.uuid4())

        # Calculate content hash
        if isinstance(content, str):
            content = content.encode("utf-8")
        content_hash = hashlib.sha256(content).hexdigest() if content else ""

        doc = ComplianceDocument(
            doc_id=doc_id,
            title=title,
            document_type=document_type,
            framework=framework,
            author=author,
            content_hash=content_hash,
            file_path=file_path,
            tags=tags or [],
        )
        self.documents[doc_id] = doc

        logger.info(f"Document registered: {title} ({doc_id})")
        return doc

    def update_document(
        self,
        doc_id: str,
        content: str | bytes = "",
        approver: str = "",
    ) -> bool:
        """Update a document and increment version."""
        if doc_id not in self.documents:
            return False

        doc = self.documents[doc_id]

        # Increment version
        major, minor, patch = map(int, doc.version.split("."))
        doc.version = f"{major}.{minor}.{patch + 1}"
        doc.last_updated = datetime.utcnow()

        if approver:
            doc.approver = approver

        if content:
            if isinstance(content, str):
                content = content.encode("utf-8")
            doc.content_hash = hashlib.sha256(content).hexdigest()

        return True

    def get_by_framework(
        self, framework: ComplianceFramework
    ) -> list[ComplianceDocument]:
        """Get all documents for a framework."""
        return [d for d in self.documents.values() if d.framework == framework]

    def get_by_type(self, document_type: DocumentType) -> list[ComplianceDocument]:
        """Get all documents of a specific type."""
        return [d for d in self.documents.values() if d.document_type == document_type]

    def search_by_tags(self, tags: list[str]) -> list[ComplianceDocument]:
        """Search documents by tags."""
        return [
            d for d in self.documents.values() if any(tag in d.tags for tag in tags)
        ]


# =============================================================================
# Evidence Collector
# =============================================================================


class EvidenceCollector:
    """
    Collects and manages compliance evidence.

    Supports evidence collection for all compliance frameworks.
    """

    def __init__(self) -> None:
        self.evidence: dict[str, EvidenceItem] = {}

    def collect_evidence(
        self,
        title: str,
        description: str,
        framework: ComplianceFramework,
        control_id: str,
        collector: str,
        evidence_type: str,
        content: str | bytes = "",
        file_path: str = "",
    ) -> EvidenceItem:
        """
        Collect an evidence item.

        Args:
            title: Evidence title
            description: Evidence description
            framework: Related compliance framework
            control_id: Control being evidenced
            collector: Person collecting evidence
            evidence_type: Type of evidence
            content: Evidence content
            file_path: Path to evidence file

        Returns:
            EvidenceItem
        """
        import uuid

        evidence_id = str(uuid.uuid4())

        # Calculate content hash
        if isinstance(content, str):
            content = content.encode("utf-8")
        content_hash = hashlib.sha256(content).hexdigest() if content else ""

        item = EvidenceItem(
            evidence_id=evidence_id,
            title=title,
            description=description,
            framework=framework,
            control_id=control_id,
            collector=collector,
            evidence_type=evidence_type,
            file_path=file_path,
            content_hash=content_hash,
        )
        self.evidence[evidence_id] = item

        logger.info(f"Evidence collected: {title} for {control_id}")
        return item

    def get_evidence_for_control(self, control_id: str) -> list[EvidenceItem]:
        """Get all evidence for a specific control."""
        return [e for e in self.evidence.values() if e.control_id == control_id]

    def get_evidence_by_framework(
        self, framework: ComplianceFramework
    ) -> list[EvidenceItem]:
        """Get all evidence for a framework."""
        return [e for e in self.evidence.values() if e.framework == framework]

    def get_evidence_summary(self) -> dict[str, Any]:
        """Get summary of collected evidence."""
        by_framework: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for item in self.evidence.values():
            fw = item.framework.value
            by_framework[fw] = by_framework.get(fw, 0) + 1
            by_type[item.evidence_type] = by_type.get(item.evidence_type, 0) + 1

        return {
            "total_items": len(self.evidence),
            "by_framework": by_framework,
            "by_type": by_type,
        }


# =============================================================================
# Audit Trail Manager
# =============================================================================


class AuditTrailManager:
    """
    Manages compliance audit trails.

    Provides immutable audit logging for compliance activities.
    """

    def __init__(self) -> None:
        self.entries: list[AuditTrailEntry] = []

    def log_action(
        self,
        action: str,
        actor: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
        ip_address: str = "",
        framework: ComplianceFramework | None = None,
    ) -> AuditTrailEntry:
        """
        Log an action to the audit trail.

        Args:
            action: Action performed
            actor: Who performed the action
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            details: Additional details
            ip_address: Source IP
            framework: Related framework

        Returns:
            AuditTrailEntry
        """
        import uuid

        entry = AuditTrailEntry(
            entry_id=str(uuid.uuid4()),
            action=action,
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            framework=framework,
        )
        self.entries.append(entry)

        logger.debug(f"Audit: {action} by {actor} on {resource_type}/{resource_id}")
        return entry

    def get_entries_for_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> list[AuditTrailEntry]:
        """Get audit entries for a specific resource."""
        return [
            e
            for e in self.entries
            if e.resource_type == resource_type and e.resource_id == resource_id
        ]

    def get_entries_by_actor(self, actor: str) -> list[AuditTrailEntry]:
        """Get audit entries by actor."""
        return [e for e in self.entries if e.actor == actor]

    def get_entries_in_period(
        self,
        start: datetime,
        end: datetime,
    ) -> list[AuditTrailEntry]:
        """Get audit entries within a time period."""
        return [e for e in self.entries if start <= e.timestamp <= end]

    def export_audit_log(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Export audit log as JSON-serializable list."""
        entries = self.entries
        if start:
            entries = [e for e in entries if e.timestamp >= start]
        if end:
            entries = [e for e in entries if e.timestamp <= end]

        return [
            {
                "entry_id": e.entry_id,
                "timestamp": e.timestamp.isoformat(),
                "action": e.action,
                "actor": e.actor,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": e.details,
                "ip_address": e.ip_address,
                "framework": e.framework.value if e.framework else None,
            }
            for e in entries
        ]


# =============================================================================
# Report Generator
# =============================================================================


class ReportGenerator:
    """
    Generates compliance reports.

    Creates comprehensive reports for single or multiple frameworks.
    """

    def __init__(
        self,
        gdpr_compliance: Any = None,
        soc2_compliance: Any = None,
        hipaa_compliance: Any = None,
        eu_ai_act_compliance: Any = None,
    ):
        self.gdpr = gdpr_compliance
        self.soc2 = soc2_compliance
        self.hipaa = hipaa_compliance
        self.eu_ai_act = eu_ai_act_compliance

    def generate_framework_report(
        self,
        framework: ComplianceFramework,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> ComplianceReport:
        """
        Generate report for a single framework.

        Args:
            framework: Framework to report on
            period_start: Report period start
            period_end: Report period end

        Returns:
            ComplianceReport
        """
        import uuid

        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            title=f"{framework.value.upper()} Compliance Report",
            period_start=period_start,
            period_end=period_end or datetime.utcnow(),
            frameworks=[framework],
        )

        # Get framework-specific data
        if framework == ComplianceFramework.GDPR and self.gdpr:
            data = self.gdpr.get_compliance_status()
            report.overall_score = data.get("compliance_score", 0)
            report.status = (
                AuditStatus.COMPLETED
                if data.get("is_compliant")
                else AuditStatus.IN_PROGRESS
            )
        elif framework == ComplianceFramework.SOC2 and self.soc2:
            data = self.soc2.get_compliance_report()
            report.overall_score = data.get("overall_score", 0)
        elif framework == ComplianceFramework.HIPAA and self.hipaa:
            data = self.hipaa.get_compliance_report()
            report.overall_score = data.get("overall_score", 0)
            status = data.get("status", "non_compliant")
            report.status = (
                AuditStatus.COMPLETED
                if status == "compliant"
                else AuditStatus.IN_PROGRESS
            )
        elif framework == ComplianceFramework.EU_AI_ACT and self.eu_ai_act:
            # EU AI Act reports per system, summarize here
            report.overall_score = 0
            report.status = AuditStatus.IN_PROGRESS

        report.framework_scores[framework.value] = report.overall_score

        return report

    def generate_unified_report(
        self,
        frameworks: list[ComplianceFramework] | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> ComplianceReport:
        """
        Generate unified report across multiple frameworks.

        Args:
            frameworks: Frameworks to include (all if None)
            period_start: Report period start
            period_end: Report period end

        Returns:
            ComplianceReport
        """
        import uuid

        if frameworks is None:
            frameworks = list(ComplianceFramework)

        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            title="Unified Compliance Report",
            period_start=period_start,
            period_end=period_end or datetime.utcnow(),
            frameworks=frameworks,
        )

        total_score = 0.0
        scores_count = 0

        for framework in frameworks:
            fw_report = self.generate_framework_report(
                framework, period_start, period_end
            )
            if fw_report.overall_score > 0:
                report.framework_scores[framework.value] = fw_report.overall_score
                total_score += fw_report.overall_score
                scores_count += 1

        if scores_count > 0:
            report.overall_score = total_score / scores_count

        # Determine overall status
        if report.overall_score >= 90:
            report.status = AuditStatus.COMPLETED
        elif report.overall_score >= 60:
            report.status = AuditStatus.IN_PROGRESS
        else:
            report.status = AuditStatus.PENDING_REVIEW

        # Generate executive summary
        report.executive_summary = self._generate_executive_summary(report)

        return report

    def _generate_executive_summary(self, report: ComplianceReport) -> str:
        """Generate executive summary for report."""
        frameworks_str = ", ".join(fw.value.upper() for fw in report.frameworks)
        status_str = report.status.value.replace("_", " ").title()

        return (
            f"This report covers compliance assessment for: {frameworks_str}. "
            f"Overall compliance score: {report.overall_score:.1f}%. "
            f"Status: {status_str}. "
            f"Report generated on {report.generated_date.strftime('%Y-%m-%d')}."
        )


# =============================================================================
# Compliance Package Exporter
# =============================================================================


class CompliancePackageExporter:
    """
    Exports compliance documentation packages.

    Creates structured packages for regulatory submissions.
    """

    def __init__(
        self,
        document_registry: DocumentRegistry,
        evidence_collector: EvidenceCollector,
        audit_trail: AuditTrailManager,
        report_generator: ReportGenerator,
    ):
        self.documents = document_registry
        self.evidence = evidence_collector
        self.audit_trail = audit_trail
        self.reports = report_generator

    def create_package_manifest(
        self,
        frameworks: list[ComplianceFramework],
        include_evidence: bool = True,
        include_audit_trail: bool = True,
    ) -> dict[str, Any]:
        """
        Create a package manifest.

        Args:
            frameworks: Frameworks to include
            include_evidence: Include evidence items
            include_audit_trail: Include audit trail

        Returns:
            Package manifest dictionary
        """
        documents_list: list[dict[str, Any]] = []
        evidence_list: list[dict[str, Any]] = []
        manifest: dict[str, Any] = {
            "package_id": hashlib.sha256(
                datetime.utcnow().isoformat().encode()
            ).hexdigest()[:16],
            "created_date": datetime.utcnow().isoformat(),
            "frameworks": [fw.value for fw in frameworks],
            "documents": documents_list,
            "evidence": evidence_list,
            "audit_entries_count": 0,
            "compliance_report": None,
        }

        # Collect documents
        for framework in frameworks:
            docs = self.documents.get_by_framework(framework)
            for doc in docs:
                manifest["documents"].append(
                    {
                        "doc_id": doc.doc_id,
                        "title": doc.title,
                        "type": doc.document_type.value,
                        "framework": doc.framework.value,
                        "version": doc.version,
                        "content_hash": doc.content_hash,
                    }
                )

        # Collect evidence
        if include_evidence:
            for framework in frameworks:
                items = self.evidence.get_evidence_by_framework(framework)
                for item in items:
                    manifest["evidence"].append(
                        {
                            "evidence_id": item.evidence_id,
                            "title": item.title,
                            "framework": item.framework.value,
                            "control_id": item.control_id,
                            "content_hash": item.content_hash,
                        }
                    )

        # Audit trail count
        if include_audit_trail:
            manifest["audit_entries_count"] = len(self.audit_trail.entries)

        # Generate unified report
        report = self.reports.generate_unified_report(frameworks)
        manifest["compliance_report"] = {
            "report_id": report.report_id,
            "overall_score": report.overall_score,
            "status": report.status.value,
            "framework_scores": report.framework_scores,
        }

        return manifest

    def export_to_json(
        self,
        frameworks: list[ComplianceFramework],
        output_path: str | Path | None = None,
    ) -> str:
        """
        Export package to JSON.

        Args:
            frameworks: Frameworks to include
            output_path: Optional output file path

        Returns:
            JSON string
        """
        manifest = self.create_package_manifest(frameworks)
        json_str = json.dumps(manifest, indent=2, default=str)

        if output_path:
            path = Path(output_path)
            path.write_text(json_str)
            logger.info(f"Package exported to {output_path}")

        return json_str


# =============================================================================
# Compliance Documentation Manager
# =============================================================================


class ComplianceDocumentationManager:
    """
    Central manager for compliance documentation.

    Integrates all documentation components:
    - Document Registry
    - Evidence Collection
    - Audit Trail
    - Report Generation
    - Package Export
    """

    def __init__(
        self,
        organization_name: str = "WarmLogic",
        gdpr_compliance: Any = None,
        soc2_compliance: Any = None,
        hipaa_compliance: Any = None,
        eu_ai_act_compliance: Any = None,
    ):
        self.organization_name = organization_name

        # Initialize components
        self.documents = DocumentRegistry()
        self.evidence = EvidenceCollector()
        self.audit_trail = AuditTrailManager()
        self.report_generator = ReportGenerator(
            gdpr_compliance=gdpr_compliance,
            soc2_compliance=soc2_compliance,
            hipaa_compliance=hipaa_compliance,
            eu_ai_act_compliance=eu_ai_act_compliance,
        )
        self.exporter = CompliancePackageExporter(
            document_registry=self.documents,
            evidence_collector=self.evidence,
            audit_trail=self.audit_trail,
            report_generator=self.report_generator,
        )

        self._initialized = False

    def initialize(self) -> bool:
        """Initialize documentation manager."""
        self._initialized = True
        self.audit_trail.log_action(
            action="initialize",
            actor="system",
            resource_type="documentation_manager",
            resource_id=self.organization_name,
        )
        logger.info(
            f"Compliance documentation initialized for {self.organization_name}"
        )
        return True

    def register_policy(
        self,
        title: str,
        framework: ComplianceFramework,
        author: str,
        content: str = "",
    ) -> ComplianceDocument:
        """Register a compliance policy document."""
        doc = self.documents.register_document(
            title=title,
            document_type=DocumentType.POLICY,
            framework=framework,
            author=author,
            content=content,
            tags=["policy", framework.value],
        )
        self.audit_trail.log_action(
            action="register_policy",
            actor=author,
            resource_type="document",
            resource_id=doc.doc_id,
            framework=framework,
        )
        return doc

    def register_procedure(
        self,
        title: str,
        framework: ComplianceFramework,
        author: str,
        content: str = "",
    ) -> ComplianceDocument:
        """Register a compliance procedure document."""
        doc = self.documents.register_document(
            title=title,
            document_type=DocumentType.PROCEDURE,
            framework=framework,
            author=author,
            content=content,
            tags=["procedure", framework.value],
        )
        self.audit_trail.log_action(
            action="register_procedure",
            actor=author,
            resource_type="document",
            resource_id=doc.doc_id,
            framework=framework,
        )
        return doc

    def collect_control_evidence(
        self,
        title: str,
        description: str,
        framework: ComplianceFramework,
        control_id: str,
        collector: str,
        evidence_type: str,
        content: str = "",
    ) -> EvidenceItem:
        """Collect evidence for a control."""
        item = self.evidence.collect_evidence(
            title=title,
            description=description,
            framework=framework,
            control_id=control_id,
            collector=collector,
            evidence_type=evidence_type,
            content=content,
        )
        self.audit_trail.log_action(
            action="collect_evidence",
            actor=collector,
            resource_type="evidence",
            resource_id=item.evidence_id,
            details={"control_id": control_id},
            framework=framework,
        )
        return item

    def generate_report(
        self,
        frameworks: list[ComplianceFramework] | None = None,
    ) -> ComplianceReport:
        """Generate a compliance report."""
        report = self.report_generator.generate_unified_report(frameworks)
        self.audit_trail.log_action(
            action="generate_report",
            actor="system",
            resource_type="report",
            resource_id=report.report_id,
        )
        return report

    def export_package(
        self,
        frameworks: list[ComplianceFramework] | None = None,
        output_path: str | Path | None = None,
    ) -> str:
        """Export compliance documentation package."""
        if frameworks is None:
            frameworks = list(ComplianceFramework)

        result = self.exporter.export_to_json(frameworks, output_path)
        self.audit_trail.log_action(
            action="export_package",
            actor="system",
            resource_type="package",
            resource_id="export",
            details={"frameworks": [fw.value for fw in frameworks]},
        )
        return result

    def get_status_summary(self) -> dict[str, Any]:
        """Get documentation status summary."""
        return {
            "organization": self.organization_name,
            "initialized": self._initialized,
            "documents": {
                "total": len(self.documents.documents),
                "by_type": {
                    dt.value: len(self.documents.get_by_type(dt)) for dt in DocumentType
                },
                "by_framework": {
                    fw.value: len(self.documents.get_by_framework(fw))
                    for fw in ComplianceFramework
                },
            },
            "evidence": self.evidence.get_evidence_summary(),
            "audit_trail_entries": len(self.audit_trail.entries),
        }
