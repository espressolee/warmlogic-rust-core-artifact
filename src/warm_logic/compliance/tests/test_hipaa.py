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
[Q3 2026] HIPAA Compliance Tests

Tests for HIPAA compliance infrastructure including:
- PHI data handling and minimum necessary standard
- Security safeguards registry
- Business associate management
- Breach notification
- Risk analysis
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from warm_logic.compliance.hipaa import (
    BreachNotificationManager,
    BreachSeverity,
    BusinessAssociate,
    BusinessAssociateManager,
    DisclosureType,
    HIPAACompliance,
    PHIAccessLog,
    PHICategory,
    PHIDataHandler,
    PHIRecord,
    RiskAnalysis,
    RiskAnalysisManager,
    SafeguardsRegistry,
    SafeguardType,
)

# =============================================================================
# PHI Data Handler Tests
# =============================================================================


class TestPHIDataHandler(unittest.TestCase):
    """Test PHI data handling functionality."""

    def setUp(self):
        self.handler = PHIDataHandler()

    def test_register_phi(self):
        """Test PHI registration creates record with hash."""
        record = self.handler.register_phi(
            patient_id="patient123",
            category=PHICategory.MEDICAL,
            data="sensitive medical data",
        )
        self.assertIsInstance(record, PHIRecord)
        self.assertEqual(record.patient_id, "patient123")
        self.assertEqual(record.category, PHICategory.MEDICAL)
        # Should store hash, not actual data
        self.assertIsNotNone(record.data_hash)
        self.assertNotEqual(record.data_hash, "sensitive medical data")

    def test_register_phi_with_bytes(self):
        """Test PHI registration with bytes data."""
        record = self.handler.register_phi(
            patient_id="patient456",
            category=PHICategory.DEMOGRAPHIC,
            data=b"binary data",
        )
        self.assertIsNotNone(record.data_hash)

    def test_set_access_policy(self):
        """Test setting role-based access policies."""
        self.handler.set_access_policy(
            role="physician",
            allowed_categories=[PHICategory.MEDICAL, PHICategory.DEMOGRAPHIC],
        )
        self.assertIn("physician", self.handler._access_policies)
        self.assertIn(PHICategory.MEDICAL, self.handler._access_policies["physician"])

    def test_check_access_allowed(self):
        """Test access check for authorized role."""
        record = self.handler.register_phi(
            patient_id="patient123",
            category=PHICategory.MEDICAL,
            data="test data",
        )
        self.handler.set_access_policy(
            role="physician",
            allowed_categories=[PHICategory.MEDICAL],
        )

        allowed, reason = self.handler.check_access(
            user_id="doc1",
            user_role="physician",
            record_id=record.record_id,
            purpose=DisclosureType.TREATMENT,
        )
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_check_access_denied_wrong_role(self):
        """Test access denied for unauthorized role."""
        record = self.handler.register_phi(
            patient_id="patient123",
            category=PHICategory.MEDICAL,
            data="test data",
        )
        self.handler.set_access_policy(
            role="billing",
            allowed_categories=[PHICategory.PAYMENT],
        )

        allowed, reason = self.handler.check_access(
            user_id="clerk1",
            user_role="billing",
            record_id=record.record_id,
            purpose=DisclosureType.PAYMENT,
        )
        self.assertFalse(allowed)
        self.assertIn("not authorized", reason)

    def test_check_access_record_not_found(self):
        """Test access check for non-existent record."""
        allowed, reason = self.handler.check_access(
            user_id="doc1",
            user_role="physician",
            record_id="nonexistent",
            purpose=DisclosureType.TREATMENT,
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "Record not found")

    def test_enhanced_protection_genetic_data(self):
        """Test enhanced protection for genetic data."""
        record = self.handler.register_phi(
            patient_id="patient123",
            category=PHICategory.GENETIC,
            data="genetic test results",
        )
        self.handler.set_access_policy(
            role="researcher",
            allowed_categories=[PHICategory.GENETIC],
        )

        # Research purpose should be denied for genetic data
        allowed, reason = self.handler.check_access(
            user_id="researcher1",
            user_role="researcher",
            record_id=record.record_id,
            purpose=DisclosureType.RESEARCH,
        )
        self.assertFalse(allowed)
        self.assertIn("Enhanced protection", reason)

        # Treatment purpose should be allowed
        allowed, reason = self.handler.check_access(
            user_id="researcher1",
            user_role="researcher",
            record_id=record.record_id,
            purpose=DisclosureType.TREATMENT,
        )
        self.assertTrue(allowed)

    def test_access_phi_logs_access(self):
        """Test that accessing PHI creates audit log."""
        record = self.handler.register_phi(
            patient_id="patient123",
            category=PHICategory.MEDICAL,
            data="test data",
        )
        self.handler.set_access_policy(
            role="physician",
            allowed_categories=[PHICategory.MEDICAL],
        )

        log_entry = self.handler.access_phi(
            user_id="doc1",
            user_role="physician",
            record_id=record.record_id,
            action="view",
            purpose=DisclosureType.TREATMENT,
            ip_address="192.168.1.1",
        )

        self.assertIsInstance(log_entry, PHIAccessLog)
        self.assertTrue(log_entry.success)
        self.assertEqual(log_entry.action, "view")
        self.assertEqual(len(self.handler.access_logs), 1)

    def test_access_phi_increments_access_count(self):
        """Test that successful access increments count."""
        record = self.handler.register_phi(
            patient_id="patient123",
            category=PHICategory.MEDICAL,
            data="test data",
        )
        self.handler.set_access_policy(
            role="physician",
            allowed_categories=[PHICategory.MEDICAL],
        )

        self.handler.access_phi(
            user_id="doc1",
            user_role="physician",
            record_id=record.record_id,
            action="view",
            purpose=DisclosureType.TREATMENT,
        )

        self.assertEqual(record.access_count, 1)
        self.assertIsNotNone(record.last_accessed)

    def test_get_access_history_filtered(self):
        """Test filtering access history."""
        record = self.handler.register_phi(
            patient_id="patient123",
            category=PHICategory.MEDICAL,
            data="test data",
        )
        self.handler.set_access_policy(
            role="physician",
            allowed_categories=[PHICategory.MEDICAL],
        )

        self.handler.access_phi(
            user_id="doc1",
            user_role="physician",
            record_id=record.record_id,
            action="view",
            purpose=DisclosureType.TREATMENT,
        )
        self.handler.access_phi(
            user_id="doc2",
            user_role="physician",
            record_id=record.record_id,
            action="modify",
            purpose=DisclosureType.TREATMENT,
        )

        # Filter by user
        logs = self.handler.get_access_history(user_id="doc1")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].user_id, "doc1")


# =============================================================================
# Safeguards Registry Tests
# =============================================================================


class TestSafeguardsRegistry(unittest.TestCase):
    """Test security safeguards registry."""

    def setUp(self):
        self.registry = SafeguardsRegistry()

    def test_initial_safeguards_created(self):
        """Test that required safeguards are initialized."""
        # Should have administrative, physical, and technical safeguards
        self.assertGreater(len(self.registry.safeguards), 0)

    def test_add_custom_safeguard(self):
        """Test adding custom safeguard."""
        safeguard = self.registry.add_safeguard(
            name="custom_encryption",
            safeguard_type=SafeguardType.TECHNICAL,
            description="Custom encryption implementation",
            required=False,
        )
        self.assertIn(safeguard.safeguard_id, self.registry.safeguards)

    def test_update_safeguard_status(self):
        """Test updating safeguard implementation status."""
        safeguard = self.registry.add_safeguard(
            name="test_safeguard",
            safeguard_type=SafeguardType.TECHNICAL,
            description="Test safeguard",
        )

        result = self.registry.update_status(
            safeguard_id=safeguard.safeguard_id,
            status="implemented",
            evidence_location="/docs/evidence/test.pdf",
        )

        self.assertTrue(result)
        self.assertEqual(safeguard.implementation_status, "implemented")
        self.assertEqual(safeguard.evidence_location, "/docs/evidence/test.pdf")
        self.assertIsNotNone(safeguard.last_review_date)

    def test_update_nonexistent_safeguard(self):
        """Test updating non-existent safeguard."""
        result = self.registry.update_status(
            safeguard_id="nonexistent",
            status="implemented",
        )
        self.assertFalse(result)

    def test_get_by_type(self):
        """Test filtering safeguards by type."""
        admin_safeguards = self.registry.get_by_type(SafeguardType.ADMINISTRATIVE)
        self.assertGreater(len(admin_safeguards), 0)
        for s in admin_safeguards:
            self.assertEqual(s.safeguard_type, SafeguardType.ADMINISTRATIVE)

    def test_get_compliance_status(self):
        """Test compliance status calculation."""
        status = self.registry.get_compliance_status()

        self.assertIn("total_safeguards", status)
        self.assertIn("implemented", status)
        self.assertIn("required_compliance", status)
        self.assertIn("by_type", status)
        self.assertIn("administrative", status["by_type"])


# =============================================================================
# Business Associate Manager Tests
# =============================================================================


class TestBusinessAssociateManager(unittest.TestCase):
    """Test business associate management."""

    def setUp(self):
        self.manager = BusinessAssociateManager()

    def test_register_associate(self):
        """Test registering a business associate."""
        ba = self.manager.register_associate(
            organization_name="Cloud Provider Inc",
            contact_email="security@cloudprovider.com",
            services_provided=["hosting", "backup"],
            phi_access_level="limited",
        )

        self.assertIsInstance(ba, BusinessAssociate)
        self.assertEqual(ba.organization_name, "Cloud Provider Inc")
        self.assertTrue(ba.is_active)
        self.assertIn(ba.ba_id, self.manager.associates)

    def test_add_subcontractor(self):
        """Test adding subcontractor to business associate."""
        ba = self.manager.register_associate(
            organization_name="Main Vendor",
            contact_email="vendor@example.com",
            services_provided=["analytics"],
        )

        result = self.manager.add_subcontractor(ba.ba_id, "Sub Vendor LLC")
        self.assertTrue(result)
        self.assertIn("Sub Vendor LLC", ba.subcontractors)

    def test_add_subcontractor_invalid_ba(self):
        """Test adding subcontractor to invalid BA."""
        result = self.manager.add_subcontractor("invalid_id", "Sub Vendor")
        self.assertFalse(result)

    def test_record_audit(self):
        """Test recording compliance audit."""
        ba = self.manager.register_associate(
            organization_name="Vendor",
            contact_email="vendor@example.com",
            services_provided=["service"],
        )

        result = self.manager.record_audit(ba.ba_id)
        self.assertTrue(result)
        self.assertIsNotNone(ba.last_audit_date)

    def test_check_expiring_agreements(self):
        """Test checking for expiring agreements."""
        # Register with short expiration
        ba = self.manager.register_associate(
            organization_name="Short Term Vendor",
            contact_email="vendor@example.com",
            services_provided=["service"],
            agreement_duration_days=15,
        )

        expiring = self.manager.check_expiring(within_days=30)
        self.assertEqual(len(expiring), 1)
        self.assertEqual(expiring[0].ba_id, ba.ba_id)

    def test_deactivate_associate(self):
        """Test deactivating a business associate."""
        ba = self.manager.register_associate(
            organization_name="Former Vendor",
            contact_email="vendor@example.com",
            services_provided=["service"],
        )

        result = self.manager.deactivate(ba.ba_id)
        self.assertTrue(result)
        self.assertFalse(ba.is_active)

    def test_phi_access_summary(self):
        """Test PHI access summary generation."""
        self.manager.register_associate(
            organization_name="Full Access Vendor",
            contact_email="full@example.com",
            services_provided=["service"],
            phi_access_level="full",
        )
        self.manager.register_associate(
            organization_name="Limited Access Vendor",
            contact_email="limited@example.com",
            services_provided=["service"],
            phi_access_level="limited",
        )

        summary = self.manager.get_phi_access_summary()
        self.assertIn("full_access", summary)
        self.assertIn("limited_access", summary)
        self.assertEqual(len(summary["full_access"]), 1)
        self.assertEqual(len(summary["limited_access"]), 1)


# =============================================================================
# Breach Notification Manager Tests
# =============================================================================


class TestBreachNotificationManager(unittest.TestCase):
    """Test breach notification management."""

    def setUp(self):
        self.notifications_sent = []
        self.manager = BreachNotificationManager(
            notification_callback=lambda incident: self.notifications_sent.append(
                incident
            )
        )

    def test_report_breach_auto_severity(self):
        """Test breach reporting with auto severity calculation."""
        incident = self.manager.report_breach(
            description="Data breach in backup system",
            phi_categories=[PHICategory.MEDICAL],
            individuals_affected=50,
        )

        self.assertIsNotNone(incident.incident_id)
        self.assertEqual(incident.severity, BreachSeverity.MEDIUM)
        self.assertTrue(incident.notification_required)

    def test_report_breach_high_severity(self):
        """Test high severity breach for many individuals."""
        incident = self.manager.report_breach(
            description="Large scale breach",
            phi_categories=[PHICategory.DEMOGRAPHIC],
            individuals_affected=200,
        )
        self.assertEqual(incident.severity, BreachSeverity.HIGH)

    def test_report_breach_critical_genetic(self):
        """Test critical severity for genetic data breach."""
        incident = self.manager.report_breach(
            description="Genetic data exposed",
            phi_categories=[PHICategory.GENETIC],
            individuals_affected=5,
        )
        self.assertEqual(incident.severity, BreachSeverity.CRITICAL)

    def test_report_breach_critical_large_scale(self):
        """Test critical severity for 500+ individuals."""
        incident = self.manager.report_breach(
            description="Major breach",
            phi_categories=[PHICategory.DEMOGRAPHIC],
            individuals_affected=600,
        )
        self.assertEqual(incident.severity, BreachSeverity.CRITICAL)

    def test_send_notifications(self):
        """Test sending breach notifications."""
        incident = self.manager.report_breach(
            description="Test breach",
            phi_categories=[PHICategory.MEDICAL],
            individuals_affected=100,
        )

        result = self.manager.send_notifications(incident.incident_id)
        self.assertTrue(result["success"])
        self.assertTrue(result["individuals_notified"])
        self.assertEqual(len(self.notifications_sent), 1)
        self.assertIsNotNone(incident.notification_sent_date)

    def test_send_notifications_hhs(self):
        """Test HHS notification for large breach."""
        incident = self.manager.report_breach(
            description="Large breach",
            phi_categories=[PHICategory.MEDICAL],
            individuals_affected=600,
        )

        result = self.manager.send_notifications(incident.incident_id)
        self.assertTrue(result["hhs_notified"])
        self.assertTrue(result["media_notified"])
        self.assertTrue(incident.hhs_notified)

    def test_send_notifications_not_found(self):
        """Test notification for non-existent incident."""
        result = self.manager.send_notifications("nonexistent")
        self.assertFalse(result["success"])

    def test_resolve_incident(self):
        """Test resolving a breach incident."""
        incident = self.manager.report_breach(
            description="Test breach",
            phi_categories=[PHICategory.MEDICAL],
            individuals_affected=10,
        )

        result = self.manager.resolve_incident(
            incident_id=incident.incident_id,
            root_cause="Misconfigured firewall",
            remediation_steps=["Updated firewall rules", "Conducted training"],
        )

        self.assertTrue(result)
        self.assertEqual(incident.status, "resolved")
        self.assertEqual(incident.root_cause, "Misconfigured firewall")

    def test_get_metrics(self):
        """Test breach metrics calculation."""
        self.manager.report_breach(
            description="Breach 1",
            phi_categories=[PHICategory.MEDICAL],
            individuals_affected=10,
        )
        self.manager.report_breach(
            description="Breach 2",
            phi_categories=[PHICategory.DEMOGRAPHIC],
            individuals_affected=20,
        )

        metrics = self.manager.get_metrics()
        self.assertEqual(metrics["total_incidents"], 2)
        self.assertEqual(metrics["total_individuals_affected"], 30)


# =============================================================================
# Risk Analysis Manager Tests
# =============================================================================


class TestRiskAnalysisManager(unittest.TestCase):
    """Test risk analysis management."""

    def setUp(self):
        self.manager = RiskAnalysisManager()

    def test_conduct_analysis(self):
        """Test conducting risk analysis."""
        analysis = self.manager.conduct_analysis(
            conducted_by="Security Team",
            scope="Full system audit",
            threats=["Phishing", "Ransomware"],
            vulnerabilities=["Outdated software", "Weak passwords"],
            risk_level="high",
        )

        self.assertIsInstance(analysis, RiskAnalysis)
        self.assertEqual(len(analysis.threats_identified), 2)
        self.assertEqual(analysis.risk_level, "high")
        self.assertIn(analysis.analysis_id, self.manager.analyses)

    def test_add_mitigation(self):
        """Test adding mitigation plan."""
        analysis = self.manager.conduct_analysis(
            conducted_by="Security Team",
            scope="Test scope",
            threats=["Test threat"],
            vulnerabilities=["Test vulnerability"],
        )

        result = self.manager.add_mitigation(
            analysis_id=analysis.analysis_id,
            risk_item="Test threat",
            mitigation_plan="Implement controls",
            responsible_party="IT Team",
            target_date=datetime.utcnow() + timedelta(days=30),
        )

        self.assertTrue(result)
        self.assertIn("mitigations", analysis.mitigation_plan)
        self.assertEqual(len(analysis.mitigation_plan["mitigations"]), 1)

    def test_add_mitigation_invalid_analysis(self):
        """Test adding mitigation to invalid analysis."""
        result = self.manager.add_mitigation(
            analysis_id="invalid",
            risk_item="Risk",
            mitigation_plan="Plan",
            responsible_party="Team",
        )
        self.assertFalse(result)

    def test_get_overdue_reviews(self):
        """Test getting overdue reviews."""
        # Create analysis with past review date
        analysis = self.manager.conduct_analysis(
            conducted_by="Team",
            scope="Scope",
            threats=[],
            vulnerabilities=[],
            review_interval_days=-1,  # Already overdue
        )

        overdue = self.manager.get_overdue_reviews()
        self.assertEqual(len(overdue), 1)

    def test_get_high_risk_items(self):
        """Test getting high risk items."""
        self.manager.conduct_analysis(
            conducted_by="Team",
            scope="Low risk scope",
            threats=[],
            vulnerabilities=[],
            risk_level="low",
        )
        self.manager.conduct_analysis(
            conducted_by="Team",
            scope="High risk scope",
            threats=["Critical threat"],
            vulnerabilities=["Critical vuln"],
            risk_level="high",
        )

        high_risk = self.manager.get_high_risk_items()
        self.assertEqual(len(high_risk), 1)
        self.assertEqual(high_risk[0].risk_level, "high")


# =============================================================================
# HIPAA Compliance Central Manager Tests
# =============================================================================


class TestHIPAACompliance(unittest.TestCase):
    """Test central HIPAA compliance manager."""

    def setUp(self):
        self.compliance = HIPAACompliance(organization_name="Test Healthcare")

    def test_initialize(self):
        """Test compliance initialization."""
        result = self.compliance.initialize(compliance_officer="John Smith")
        self.assertTrue(result)
        self.assertEqual(self.compliance._compliance_officer, "John Smith")

    def test_get_compliance_report(self):
        """Test generating compliance report."""
        self.compliance.initialize()

        report = self.compliance.get_compliance_report()

        self.assertEqual(report["organization"], "Test Healthcare")
        self.assertIn("overall_score", report)
        self.assertIn("safeguards", report)
        self.assertIn("breach_metrics", report)
        self.assertIn("business_associates", report)
        self.assertIn("risk_analysis", report)
        self.assertIn("phi_handling", report)

    def test_compliance_score_calculation(self):
        """Test compliance score calculation."""
        self.compliance.initialize()

        # Add risk analysis to improve score
        self.compliance.risk_manager.conduct_analysis(
            conducted_by="Security Team",
            scope="Annual review",
            threats=["Phishing"],
            vulnerabilities=["Training gaps"],
            risk_level="medium",
        )

        report = self.compliance.get_compliance_report()
        self.assertGreater(report["overall_score"], 0)

    def test_get_audit_checklist(self):
        """Test audit checklist generation."""
        self.compliance.initialize()

        checklist = self.compliance.get_audit_checklist()

        self.assertIsInstance(checklist, list)
        self.assertGreater(len(checklist), 0)

        # Check checklist item structure
        item = checklist[0]
        self.assertIn("item", item)
        self.assertIn("requirement", item)
        self.assertIn("status", item)
        self.assertIn("notes", item)

    def test_phi_handler_integration(self):
        """Test PHI handler is properly integrated."""
        record = self.compliance.phi_handler.register_phi(
            patient_id="patient123",
            category=PHICategory.MEDICAL,
            data="test data",
        )

        report = self.compliance.get_compliance_report()
        self.assertEqual(report["phi_handling"]["total_records"], 1)

    def test_breach_manager_integration(self):
        """Test breach manager is properly integrated."""
        self.compliance.breach_manager.report_breach(
            description="Test breach",
            phi_categories=[PHICategory.MEDICAL],
            individuals_affected=10,
        )

        report = self.compliance.get_compliance_report()
        self.assertEqual(report["breach_metrics"]["total_incidents"], 1)

    def test_business_associate_integration(self):
        """Test business associate manager is integrated."""
        self.compliance.business_associates.register_associate(
            organization_name="Vendor",
            contact_email="vendor@example.com",
            services_provided=["service"],
        )

        report = self.compliance.get_compliance_report()
        self.assertEqual(report["business_associates"]["total_active"], 1)

    def test_calculate_ba_score_no_associates(self):
        """Test BA score with no associates."""
        score = self.compliance._calculate_ba_score()
        self.assertEqual(score, 100.0)

    def test_calculate_ba_score_with_audits(self):
        """Test BA score with audited associates."""
        ba = self.compliance.business_associates.register_associate(
            organization_name="Vendor",
            contact_email="vendor@example.com",
            services_provided=["service"],
        )
        self.compliance.business_associates.record_audit(ba.ba_id)

        score = self.compliance._calculate_ba_score()
        self.assertEqual(score, 100.0)

    def test_calculate_risk_score_no_analyses(self):
        """Test risk score with no analyses."""
        score = self.compliance._calculate_risk_score()
        self.assertEqual(score, 50.0)  # Needs improvement

    def test_compliance_status_thresholds(self):
        """Test compliance status based on score thresholds."""
        self.compliance.initialize()

        # Mock high compliance by marking safeguards as implemented
        for safeguard_id in list(self.compliance.safeguards.safeguards.keys())[:10]:
            self.compliance.safeguards.update_status(safeguard_id, "implemented")

        report = self.compliance.get_compliance_report()
        # Status should be based on overall_score
        self.assertIn(
            report["status"], ["compliant", "needs_improvement", "non_compliant"]
        )


if __name__ == "__main__":
    unittest.main()
