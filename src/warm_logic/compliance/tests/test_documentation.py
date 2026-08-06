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
[Q3 2026] Compliance Documentation Tests

Tests for compliance documentation package including:
- Document Registry
- Evidence Collection
- Audit Trail
- Report Generation
- Package Export
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from warm_logic.compliance.documentation import (
    AuditTrailEntry,
    AuditTrailManager,
    ComplianceDocument,
    ComplianceDocumentationManager,
    ComplianceFramework,
    CompliancePackageExporter,
    ComplianceReport,
    DocumentRegistry,
    DocumentType,
    EvidenceCollector,
    EvidenceItem,
    ReportGenerator,
)

# =============================================================================
# Document Registry Tests
# =============================================================================


class TestDocumentRegistry(unittest.TestCase):
    """Test document registry functionality."""

    def setUp(self):
        self.registry = DocumentRegistry()

    def test_register_document(self):
        """Test registering a document."""
        doc = self.registry.register_document(
            title="Data Protection Policy",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.GDPR,
            author="Compliance Team",
            content="Policy content here",
        )

        self.assertIsInstance(doc, ComplianceDocument)
        self.assertEqual(doc.title, "Data Protection Policy")
        self.assertIn(doc.doc_id, self.registry.documents)
        self.assertNotEqual(doc.content_hash, "")

    def test_register_document_with_tags(self):
        """Test registering document with tags."""
        doc = self.registry.register_document(
            title="Security Policy",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.SOC2,
            author="Security Team",
            tags=["security", "mandatory"],
        )

        self.assertIn("security", doc.tags)
        self.assertIn("mandatory", doc.tags)

    def test_update_document(self):
        """Test updating a document."""
        doc = self.registry.register_document(
            title="Test Doc",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.GDPR,
            author="Author",
        )
        original_version = doc.version

        result = self.registry.update_document(
            doc_id=doc.doc_id,
            content="Updated content",
            approver="Manager",
        )

        self.assertTrue(result)
        self.assertNotEqual(doc.version, original_version)
        self.assertEqual(doc.approver, "Manager")

    def test_update_nonexistent_document(self):
        """Test updating non-existent document."""
        result = self.registry.update_document(
            doc_id="nonexistent",
            content="Content",
        )
        self.assertFalse(result)

    def test_get_by_framework(self):
        """Test filtering by framework."""
        self.registry.register_document(
            title="GDPR Policy",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.GDPR,
            author="Author",
        )
        self.registry.register_document(
            title="HIPAA Policy",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.HIPAA,
            author="Author",
        )

        gdpr_docs = self.registry.get_by_framework(ComplianceFramework.GDPR)
        self.assertEqual(len(gdpr_docs), 1)
        self.assertEqual(gdpr_docs[0].title, "GDPR Policy")

    def test_get_by_type(self):
        """Test filtering by document type."""
        self.registry.register_document(
            title="Policy",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.GDPR,
            author="Author",
        )
        self.registry.register_document(
            title="Procedure",
            document_type=DocumentType.PROCEDURE,
            framework=ComplianceFramework.GDPR,
            author="Author",
        )

        policies = self.registry.get_by_type(DocumentType.POLICY)
        self.assertEqual(len(policies), 1)

    def test_search_by_tags(self):
        """Test searching by tags."""
        self.registry.register_document(
            title="Doc 1",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.GDPR,
            author="Author",
            tags=["security", "mandatory"],
        )
        self.registry.register_document(
            title="Doc 2",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.GDPR,
            author="Author",
            tags=["optional"],
        )

        results = self.registry.search_by_tags(["security"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Doc 1")


# =============================================================================
# Evidence Collector Tests
# =============================================================================


class TestEvidenceCollector(unittest.TestCase):
    """Test evidence collector functionality."""

    def setUp(self):
        self.collector = EvidenceCollector()

    def test_collect_evidence(self):
        """Test collecting evidence."""
        item = self.collector.collect_evidence(
            title="Access Control Screenshot",
            description="Screenshot showing access controls",
            framework=ComplianceFramework.SOC2,
            control_id="CC6.1",
            collector="Auditor",
            evidence_type="screenshot",
            content="image data here",
        )

        self.assertIsInstance(item, EvidenceItem)
        self.assertEqual(item.control_id, "CC6.1")
        self.assertIn(item.evidence_id, self.collector.evidence)

    def test_get_evidence_for_control(self):
        """Test getting evidence for a control."""
        self.collector.collect_evidence(
            title="Evidence 1",
            description="Desc",
            framework=ComplianceFramework.SOC2,
            control_id="CC6.1",
            collector="Auditor",
            evidence_type="screenshot",
        )
        self.collector.collect_evidence(
            title="Evidence 2",
            description="Desc",
            framework=ComplianceFramework.SOC2,
            control_id="CC6.2",
            collector="Auditor",
            evidence_type="report",
        )

        evidence = self.collector.get_evidence_for_control("CC6.1")
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].title, "Evidence 1")

    def test_get_evidence_by_framework(self):
        """Test getting evidence by framework."""
        self.collector.collect_evidence(
            title="GDPR Evidence",
            description="Desc",
            framework=ComplianceFramework.GDPR,
            control_id="GDPR-1",
            collector="Auditor",
            evidence_type="report",
        )
        self.collector.collect_evidence(
            title="HIPAA Evidence",
            description="Desc",
            framework=ComplianceFramework.HIPAA,
            control_id="HIPAA-1",
            collector="Auditor",
            evidence_type="report",
        )

        gdpr_evidence = self.collector.get_evidence_by_framework(
            ComplianceFramework.GDPR
        )
        self.assertEqual(len(gdpr_evidence), 1)

    def test_get_evidence_summary(self):
        """Test getting evidence summary."""
        self.collector.collect_evidence(
            title="Evidence",
            description="Desc",
            framework=ComplianceFramework.GDPR,
            control_id="CTRL-1",
            collector="Auditor",
            evidence_type="screenshot",
        )

        summary = self.collector.get_evidence_summary()
        self.assertEqual(summary["total_items"], 1)
        self.assertIn("by_framework", summary)
        self.assertIn("by_type", summary)


# =============================================================================
# Audit Trail Tests
# =============================================================================


class TestAuditTrailManager(unittest.TestCase):
    """Test audit trail functionality."""

    def setUp(self):
        self.trail = AuditTrailManager()

    def test_log_action(self):
        """Test logging an action."""
        entry = self.trail.log_action(
            action="create",
            actor="user@example.com",
            resource_type="document",
            resource_id="doc-123",
            details={"title": "Test Document"},
            ip_address="192.168.1.1",
        )

        self.assertIsInstance(entry, AuditTrailEntry)
        self.assertEqual(entry.action, "create")
        self.assertEqual(len(self.trail.entries), 1)

    def test_get_entries_for_resource(self):
        """Test getting entries for a resource."""
        self.trail.log_action(
            action="create",
            actor="user1",
            resource_type="document",
            resource_id="doc-123",
        )
        self.trail.log_action(
            action="update",
            actor="user2",
            resource_type="document",
            resource_id="doc-123",
        )
        self.trail.log_action(
            action="create",
            actor="user1",
            resource_type="document",
            resource_id="doc-456",
        )

        entries = self.trail.get_entries_for_resource("document", "doc-123")
        self.assertEqual(len(entries), 2)

    def test_get_entries_by_actor(self):
        """Test getting entries by actor."""
        self.trail.log_action(
            action="create",
            actor="admin@example.com",
            resource_type="document",
            resource_id="doc-1",
        )
        self.trail.log_action(
            action="create",
            actor="user@example.com",
            resource_type="document",
            resource_id="doc-2",
        )

        admin_entries = self.trail.get_entries_by_actor("admin@example.com")
        self.assertEqual(len(admin_entries), 1)

    def test_get_entries_in_period(self):
        """Test getting entries in time period."""
        now = datetime.utcnow()
        self.trail.log_action(
            action="test",
            actor="user",
            resource_type="doc",
            resource_id="1",
        )

        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        entries = self.trail.get_entries_in_period(start, end)
        self.assertEqual(len(entries), 1)

    def test_export_audit_log(self):
        """Test exporting audit log."""
        self.trail.log_action(
            action="test",
            actor="user",
            resource_type="doc",
            resource_id="1",
            framework=ComplianceFramework.GDPR,
        )

        exported = self.trail.export_audit_log()
        self.assertEqual(len(exported), 1)
        self.assertIn("timestamp", exported[0])
        self.assertEqual(exported[0]["framework"], "gdpr")


# =============================================================================
# Report Generator Tests
# =============================================================================


class TestReportGenerator(unittest.TestCase):
    """Test report generation functionality."""

    def setUp(self):
        self.generator = ReportGenerator()

    def test_generate_framework_report(self):
        """Test generating framework report."""
        report = self.generator.generate_framework_report(
            framework=ComplianceFramework.GDPR,
        )

        self.assertIsInstance(report, ComplianceReport)
        self.assertIn(ComplianceFramework.GDPR, report.frameworks)
        self.assertIn("gdpr", report.framework_scores)

    def test_generate_unified_report(self):
        """Test generating unified report."""
        report = self.generator.generate_unified_report(
            frameworks=[ComplianceFramework.GDPR, ComplianceFramework.SOC2],
        )

        self.assertEqual(len(report.frameworks), 2)
        self.assertIsNotNone(report.executive_summary)

    def test_generate_unified_report_all_frameworks(self):
        """Test generating report for all frameworks."""
        report = self.generator.generate_unified_report()

        self.assertEqual(len(report.frameworks), 4)

    def test_executive_summary_generation(self):
        """Test executive summary generation."""
        report = self.generator.generate_unified_report(
            frameworks=[ComplianceFramework.HIPAA],
        )

        self.assertIn("HIPAA", report.executive_summary)
        self.assertIn("compliance score", report.executive_summary.lower())


# =============================================================================
# Package Exporter Tests
# =============================================================================


class TestCompliancePackageExporter(unittest.TestCase):
    """Test package exporter functionality."""

    def setUp(self):
        self.documents = DocumentRegistry()
        self.evidence = EvidenceCollector()
        self.audit_trail = AuditTrailManager()
        self.report_generator = ReportGenerator()
        self.exporter = CompliancePackageExporter(
            document_registry=self.documents,
            evidence_collector=self.evidence,
            audit_trail=self.audit_trail,
            report_generator=self.report_generator,
        )

    def test_create_package_manifest(self):
        """Test creating package manifest."""
        self.documents.register_document(
            title="Test Policy",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.GDPR,
            author="Author",
        )

        manifest = self.exporter.create_package_manifest(
            frameworks=[ComplianceFramework.GDPR],
        )

        self.assertIn("package_id", manifest)
        self.assertEqual(len(manifest["documents"]), 1)
        self.assertIn("compliance_report", manifest)

    def test_export_to_json(self):
        """Test exporting to JSON."""
        self.documents.register_document(
            title="Test Policy",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.SOC2,
            author="Author",
        )

        json_str = self.exporter.export_to_json(
            frameworks=[ComplianceFramework.SOC2],
        )

        parsed = json.loads(json_str)
        self.assertIn("package_id", parsed)

    def test_export_to_file(self):
        """Test exporting to file."""
        self.documents.register_document(
            title="Test",
            document_type=DocumentType.POLICY,
            framework=ComplianceFramework.HIPAA,
            author="Author",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            self.exporter.export_to_json(
                frameworks=[ComplianceFramework.HIPAA],
                output_path=output_path,
            )

            self.assertTrue(Path(output_path).exists())
            content = Path(output_path).read_text()
            parsed = json.loads(content)
            self.assertIn("package_id", parsed)
        finally:
            Path(output_path).unlink(missing_ok=True)


# =============================================================================
# Compliance Documentation Manager Tests
# =============================================================================


class TestComplianceDocumentationManager(unittest.TestCase):
    """Test central documentation manager."""

    def setUp(self):
        self.manager = ComplianceDocumentationManager(
            organization_name="Test Organization",
        )

    def test_initialize(self):
        """Test initialization."""
        result = self.manager.initialize()
        self.assertTrue(result)
        self.assertTrue(self.manager._initialized)
        self.assertEqual(len(self.manager.audit_trail.entries), 1)

    def test_register_policy(self):
        """Test registering a policy."""
        self.manager.initialize()

        doc = self.manager.register_policy(
            title="Privacy Policy",
            framework=ComplianceFramework.GDPR,
            author="Legal Team",
            content="Privacy policy content",
        )

        self.assertEqual(doc.document_type, DocumentType.POLICY)
        self.assertIn("policy", doc.tags)
        # Should have initialization + register action
        self.assertEqual(len(self.manager.audit_trail.entries), 2)

    def test_register_procedure(self):
        """Test registering a procedure."""
        self.manager.initialize()

        doc = self.manager.register_procedure(
            title="Incident Response Procedure",
            framework=ComplianceFramework.SOC2,
            author="Security Team",
        )

        self.assertEqual(doc.document_type, DocumentType.PROCEDURE)
        self.assertIn("procedure", doc.tags)

    def test_collect_control_evidence(self):
        """Test collecting evidence."""
        self.manager.initialize()

        item = self.manager.collect_control_evidence(
            title="Access Log",
            description="Sample access log",
            framework=ComplianceFramework.HIPAA,
            control_id="164.312(b)",
            collector="Auditor",
            evidence_type="log",
            content="Log content",
        )

        self.assertEqual(item.control_id, "164.312(b)")
        self.assertGreater(len(self.manager.audit_trail.entries), 1)

    def test_generate_report(self):
        """Test generating report."""
        self.manager.initialize()

        report = self.manager.generate_report(
            frameworks=[ComplianceFramework.GDPR],
        )

        self.assertIsInstance(report, ComplianceReport)
        self.assertIn(ComplianceFramework.GDPR, report.frameworks)

    def test_export_package(self):
        """Test exporting package."""
        self.manager.initialize()
        self.manager.register_policy(
            title="Test Policy",
            framework=ComplianceFramework.EU_AI_ACT,
            author="Author",
        )

        json_str = self.manager.export_package(
            frameworks=[ComplianceFramework.EU_AI_ACT],
        )

        parsed = json.loads(json_str)
        self.assertIn("package_id", parsed)
        self.assertEqual(len(parsed["documents"]), 1)

    def test_get_status_summary(self):
        """Test getting status summary."""
        self.manager.initialize()
        self.manager.register_policy(
            title="Policy 1",
            framework=ComplianceFramework.GDPR,
            author="Author",
        )
        self.manager.collect_control_evidence(
            title="Evidence 1",
            description="Desc",
            framework=ComplianceFramework.SOC2,
            control_id="CC1.1",
            collector="Auditor",
            evidence_type="report",
        )

        summary = self.manager.get_status_summary()

        self.assertEqual(summary["organization"], "Test Organization")
        self.assertTrue(summary["initialized"])
        self.assertEqual(summary["documents"]["total"], 1)
        self.assertEqual(summary["evidence"]["total_items"], 1)
        self.assertGreater(summary["audit_trail_entries"], 0)

    def test_full_workflow(self):
        """Test complete documentation workflow."""
        # Initialize
        self.manager.initialize()

        # Register documents
        self.manager.register_policy(
            title="Data Protection Policy",
            framework=ComplianceFramework.GDPR,
            author="Legal Team",
        )
        self.manager.register_procedure(
            title="Access Control Procedure",
            framework=ComplianceFramework.SOC2,
            author="Security Team",
        )

        # Collect evidence
        self.manager.collect_control_evidence(
            title="Access Control Config",
            description="IAM configuration",
            framework=ComplianceFramework.SOC2,
            control_id="CC6.1",
            collector="Auditor",
            evidence_type="screenshot",
        )

        # Generate report
        report = self.manager.generate_report()

        # Export package
        package_json = self.manager.export_package()

        # Verify
        summary = self.manager.get_status_summary()
        self.assertEqual(summary["documents"]["total"], 2)
        self.assertEqual(summary["evidence"]["total_items"], 1)

        package = json.loads(package_json)
        self.assertEqual(len(package["documents"]), 2)
        self.assertEqual(len(package["evidence"]), 1)


if __name__ == "__main__":
    unittest.main()
