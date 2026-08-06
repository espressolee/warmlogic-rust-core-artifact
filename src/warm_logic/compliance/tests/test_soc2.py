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
Tests for SOC 2 Compliance module.
"""

import time
import unittest

from warm_logic.compliance.soc2 import (
    AccessAuditLog,
    AccessLog,
    ChangeManagement,
    ChangeRecord,
    ControlRegistry,
    ControlStatus,
    IncidentManagement,
    IncidentSeverity,
    IncidentStatus,
    RiskAssessment,
    RiskLevel,
    RiskRegistry,
    SecurityControl,
    SecurityIncident,
    SOC2Compliance,
    TrustServiceCategory,
    get_soc2_compliance,
    initialize_soc2,
)


class TestTrustServiceCategory(unittest.TestCase):
    """Test TrustServiceCategory enum."""

    def test_categories(self):
        """Test all SOC 2 categories exist."""
        self.assertEqual(TrustServiceCategory.SECURITY.value, "security")
        self.assertEqual(TrustServiceCategory.AVAILABILITY.value, "availability")
        self.assertEqual(
            TrustServiceCategory.PROCESSING_INTEGRITY.value, "processing_integrity"
        )
        self.assertEqual(TrustServiceCategory.CONFIDENTIALITY.value, "confidentiality")
        self.assertEqual(TrustServiceCategory.PRIVACY.value, "privacy")


class TestControlStatus(unittest.TestCase):
    """Test ControlStatus enum."""

    def test_statuses(self):
        """Test all control statuses exist."""
        self.assertEqual(ControlStatus.IMPLEMENTED.value, "implemented")
        self.assertEqual(
            ControlStatus.PARTIALLY_IMPLEMENTED.value, "partially_implemented"
        )
        self.assertEqual(ControlStatus.NOT_IMPLEMENTED.value, "not_implemented")


class TestSecurityControl(unittest.TestCase):
    """Test SecurityControl dataclass."""

    def test_control_creation(self):
        """Test control creation."""
        control = SecurityControl(
            control_id="CC1.1",
            category=TrustServiceCategory.SECURITY,
            title="Security Policy",
            description="The entity has defined security policies.",
        )
        self.assertEqual(control.control_id, "CC1.1")
        self.assertEqual(control.status, ControlStatus.NOT_IMPLEMENTED)

    def test_needs_review_no_last_reviewed(self):
        """Test needs_review when never reviewed."""
        control = SecurityControl(
            control_id="CC1.1",
            category=TrustServiceCategory.SECURITY,
            title="Test",
            description="Test",
        )
        self.assertTrue(control.needs_review)

    def test_needs_review_recently_reviewed(self):
        """Test needs_review when recently reviewed."""
        control = SecurityControl(
            control_id="CC1.1",
            category=TrustServiceCategory.SECURITY,
            title="Test",
            description="Test",
            last_reviewed=time.time(),
            review_frequency_days=90,
        )
        self.assertFalse(control.needs_review)

    def test_to_dict(self):
        """Test dictionary conversion."""
        control = SecurityControl(
            control_id="CC1.1",
            category=TrustServiceCategory.SECURITY,
            title="Test",
            description="Test",
        )
        result = control.to_dict()
        self.assertEqual(result["control_id"], "CC1.1")
        self.assertEqual(result["category"], "security")


class TestAccessLog(unittest.TestCase):
    """Test AccessLog dataclass."""

    def test_log_creation(self):
        """Test access log creation."""
        log = AccessLog(
            log_id="log123",
            timestamp=time.time(),
            user_id="user456",
            action="login",
            resource="/api/v1/data",
            resource_type="api_endpoint",
            success=True,
        )
        self.assertEqual(log.action, "login")
        self.assertTrue(log.success)

    def test_to_dict(self):
        """Test dictionary conversion."""
        log = AccessLog(
            log_id="log123",
            timestamp=time.time(),
            user_id="user456",
            action="login",
            resource="/api",
            resource_type="api",
            success=True,
        )
        result = log.to_dict()
        self.assertIn("timestamp", result)
        self.assertEqual(result["action"], "login")


class TestChangeRecord(unittest.TestCase):
    """Test ChangeRecord dataclass."""

    def test_record_creation(self):
        """Test change record creation."""
        record = ChangeRecord(
            change_id="CHG001",
            title="Update API",
            description="Update API endpoint",
            change_type="standard",
            requester="developer1",
        )
        self.assertEqual(record.status, "pending")
        self.assertIsNone(record.approver)

    def test_to_dict(self):
        """Test dictionary conversion."""
        record = ChangeRecord(
            change_id="CHG001",
            title="Update API",
            description="Update API endpoint",
            change_type="standard",
            requester="developer1",
        )
        result = record.to_dict()
        self.assertEqual(result["change_type"], "standard")


class TestSecurityIncident(unittest.TestCase):
    """Test SecurityIncident dataclass."""

    def test_incident_creation(self):
        """Test incident creation."""
        incident = SecurityIncident(
            incident_id="INC001",
            title="Suspicious Login",
            description="Multiple failed login attempts",
            severity=IncidentSeverity.SEV3,
            reported_by="security_team",
        )
        self.assertEqual(incident.status, IncidentStatus.OPEN)

    def test_time_to_detect(self):
        """Test time to detect calculation."""
        incident = SecurityIncident(
            incident_id="INC001",
            title="Test",
            description="Test",
            severity=IncidentSeverity.SEV3,
            reported_by="test",
            created_at=time.time() - 3600,  # 1 hour ago
            detected_at=time.time(),
        )
        self.assertIsNotNone(incident.time_to_detect)
        self.assertAlmostEqual(incident.time_to_detect, 1.0, delta=0.1)


class TestRiskAssessment(unittest.TestCase):
    """Test RiskAssessment dataclass."""

    def test_risk_creation(self):
        """Test risk creation."""
        risk = RiskAssessment(
            risk_id="RISK001",
            title="Data Breach",
            description="Risk of data breach",
            category=TrustServiceCategory.CONFIDENTIALITY,
            likelihood=RiskLevel.MEDIUM,
            impact=RiskLevel.HIGH,
        )
        self.assertEqual(risk.status, "open")

    def test_calculate_risk_score(self):
        """Test risk score calculation."""
        risk = RiskAssessment(
            risk_id="RISK001",
            title="Test",
            description="Test",
            category=TrustServiceCategory.SECURITY,
            likelihood=RiskLevel.HIGH,
            impact=RiskLevel.HIGH,
        )
        # HIGH (4) * HIGH (4) = 16
        self.assertEqual(risk.calculate_risk_score(), 16)


class TestControlRegistry(unittest.TestCase):
    """Test ControlRegistry class."""

    def test_register_control(self):
        """Test registering a control."""
        registry = ControlRegistry()
        control = SecurityControl(
            control_id="CC1.1",
            category=TrustServiceCategory.SECURITY,
            title="Test",
            description="Test",
        )
        registry.register_control(control)

        retrieved = registry.get_control("CC1.1")
        self.assertEqual(retrieved.title, "Test")

    def test_get_controls_by_category(self):
        """Test getting controls by category."""
        registry = ControlRegistry()
        registry.register_control(
            SecurityControl(
                control_id="CC1.1",
                category=TrustServiceCategory.SECURITY,
                title="Security 1",
                description="Test",
            )
        )
        registry.register_control(
            SecurityControl(
                control_id="A1.1",
                category=TrustServiceCategory.AVAILABILITY,
                title="Availability 1",
                description="Test",
            )
        )

        security_controls = registry.get_controls_by_category(
            TrustServiceCategory.SECURITY
        )
        self.assertEqual(len(security_controls), 1)

    def test_update_status(self):
        """Test updating control status."""
        registry = ControlRegistry()
        registry.register_control(
            SecurityControl(
                control_id="CC1.1",
                category=TrustServiceCategory.SECURITY,
                title="Test",
                description="Test",
            )
        )

        result = registry.update_status(
            "CC1.1", ControlStatus.IMPLEMENTED, "Implemented on 2026-01"
        )
        self.assertTrue(result)

        control = registry.get_control("CC1.1")
        self.assertEqual(control.status, ControlStatus.IMPLEMENTED)

    def test_get_compliance_summary(self):
        """Test getting compliance summary."""
        registry = ControlRegistry()
        registry.register_control(
            SecurityControl(
                control_id="CC1.1",
                category=TrustServiceCategory.SECURITY,
                title="Test",
                description="Test",
                status=ControlStatus.IMPLEMENTED,
            )
        )

        summary = registry.get_compliance_summary()
        self.assertIn("security", summary)
        self.assertEqual(summary["security"]["implemented"], 1)


class TestAccessAuditLog(unittest.TestCase):
    """Test AccessAuditLog class."""

    def test_log_access(self):
        """Test logging an access event."""
        audit = AccessAuditLog()
        log = audit.log_access(
            user_id="user123",
            action="login",
            resource="/api/v1",
            resource_type="api",
            success=True,
        )

        self.assertIsNotNone(log.log_id)
        self.assertTrue(log.success)

    def test_get_logs_for_user(self):
        """Test getting logs for a specific user."""
        audit = AccessAuditLog()
        audit.log_access("user123", "login", "/api", "api", True)
        audit.log_access("user123", "access", "/data", "data", True)
        audit.log_access("user456", "login", "/api", "api", True)

        user123_logs = audit.get_logs_for_user("user123")
        self.assertEqual(len(user123_logs), 2)

    def test_get_failed_access_attempts(self):
        """Test getting failed access attempts."""
        audit = AccessAuditLog()
        audit.log_access("user123", "login", "/api", "api", True)
        audit.log_access("user123", "login", "/api", "api", False)
        audit.log_access("user456", "login", "/api", "api", False)

        failed = audit.get_failed_access_attempts()
        self.assertEqual(len(failed), 2)


class TestChangeManagement(unittest.TestCase):
    """Test ChangeManagement class."""

    def test_create_change_request(self):
        """Test creating a change request."""
        cm = ChangeManagement()
        change = cm.create_change_request(
            title="Update API",
            description="Update API endpoint",
            change_type="standard",
            requester="developer1",
            affected_systems=["api-service"],
        )

        self.assertIsNotNone(change.change_id)
        self.assertEqual(change.status, "pending")

    def test_approve_change(self):
        """Test approving a change."""
        cm = ChangeManagement()
        change = cm.create_change_request(
            title="Update API",
            description="Update API endpoint",
            change_type="standard",
            requester="developer1",
            affected_systems=["api-service"],
        )

        result = cm.approve_change(change.change_id, "manager1")
        self.assertTrue(result)
        self.assertEqual(change.status, "approved")
        self.assertEqual(change.approver, "manager1")

    def test_implement_change(self):
        """Test implementing a change."""
        cm = ChangeManagement()
        change = cm.create_change_request(
            title="Update API",
            description="Update",
            change_type="standard",
            requester="dev1",
            affected_systems=["api"],
        )
        cm.approve_change(change.change_id, "manager1")

        result = cm.implement_change(change.change_id, "Tests passed")
        self.assertTrue(result)
        self.assertEqual(change.status, "implemented")

    def test_get_pending_changes(self):
        """Test getting pending changes."""
        cm = ChangeManagement()
        cm.create_change_request("Change 1", "Desc", "standard", "dev1", [])
        cm.create_change_request("Change 2", "Desc", "standard", "dev2", [])

        pending = cm.get_pending_changes()
        self.assertEqual(len(pending), 2)


class TestIncidentManagement(unittest.TestCase):
    """Test IncidentManagement class."""

    def test_create_incident(self):
        """Test creating an incident."""
        im = IncidentManagement()
        incident = im.create_incident(
            title="Suspicious Login",
            description="Multiple failed login attempts",
            severity=IncidentSeverity.SEV3,
            reported_by="security_team",
        )

        self.assertIn("INC-", incident.incident_id)
        self.assertEqual(incident.status, IncidentStatus.OPEN)

    def test_assign_incident(self):
        """Test assigning an incident."""
        im = IncidentManagement()
        incident = im.create_incident(
            title="Test",
            description="Test",
            severity=IncidentSeverity.SEV3,
            reported_by="test",
        )

        result = im.assign_incident(incident.incident_id, "responder1")
        self.assertTrue(result)
        self.assertEqual(incident.assigned_to, "responder1")
        self.assertEqual(incident.status, IncidentStatus.INVESTIGATING)

    def test_mitigate_incident(self):
        """Test mitigating an incident."""
        im = IncidentManagement()
        incident = im.create_incident(
            title="Test",
            description="Test",
            severity=IncidentSeverity.SEV3,
            reported_by="test",
        )

        result = im.mitigate_incident(
            incident.incident_id, ["Blocked IP", "Reset credentials"]
        )
        self.assertTrue(result)
        self.assertEqual(incident.status, IncidentStatus.MITIGATED)

    def test_resolve_incident(self):
        """Test resolving an incident."""
        im = IncidentManagement()
        incident = im.create_incident(
            title="Test",
            description="Test",
            severity=IncidentSeverity.SEV3,
            reported_by="test",
        )

        result = im.resolve_incident(
            incident.incident_id,
            root_cause="Weak password policy",
            lessons_learned="Implement MFA",
        )
        self.assertTrue(result)
        self.assertEqual(incident.status, IncidentStatus.RESOLVED)

    def test_get_incident_metrics(self):
        """Test getting incident metrics."""
        im = IncidentManagement()
        im.create_incident("Test 1", "Test", IncidentSeverity.SEV1, "test")
        im.create_incident("Test 2", "Test", IncidentSeverity.SEV3, "test")

        metrics = im.get_incident_metrics()
        self.assertEqual(metrics["total"], 2)
        self.assertEqual(metrics["open"], 2)


class TestRiskRegistry(unittest.TestCase):
    """Test RiskRegistry class."""

    def test_register_risk(self):
        """Test registering a risk."""
        registry = RiskRegistry()
        risk = RiskAssessment(
            risk_id="RISK001",
            title="Data Breach",
            description="Risk of data breach",
            category=TrustServiceCategory.CONFIDENTIALITY,
            likelihood=RiskLevel.MEDIUM,
            impact=RiskLevel.HIGH,
        )
        registry.register_risk(risk)

        retrieved = registry.get_risk("RISK001")
        self.assertEqual(retrieved.title, "Data Breach")

    def test_get_high_risks(self):
        """Test getting high risks."""
        registry = RiskRegistry()
        registry.register_risk(
            RiskAssessment(
                risk_id="RISK001",
                title="High Risk",
                description="Test",
                category=TrustServiceCategory.SECURITY,
                likelihood=RiskLevel.HIGH,
                impact=RiskLevel.HIGH,
                residual_risk=RiskLevel.HIGH,
                status="open",
            )
        )
        registry.register_risk(
            RiskAssessment(
                risk_id="RISK002",
                title="Low Risk",
                description="Test",
                category=TrustServiceCategory.SECURITY,
                likelihood=RiskLevel.LOW,
                impact=RiskLevel.LOW,
                residual_risk=RiskLevel.LOW,
                status="open",
            )
        )

        high_risks = registry.get_high_risks()
        self.assertEqual(len(high_risks), 1)

    def test_get_risk_summary(self):
        """Test getting risk summary."""
        registry = RiskRegistry()
        registry.register_risk(
            RiskAssessment(
                risk_id="RISK001",
                title="Test",
                description="Test",
                category=TrustServiceCategory.SECURITY,
                likelihood=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
            )
        )

        summary = registry.get_risk_summary()
        self.assertEqual(summary["total"], 1)


class TestSOC2Compliance(unittest.TestCase):
    """Test SOC2Compliance class."""

    def test_initialization(self):
        """Test SOC 2 compliance initialization."""
        compliance = SOC2Compliance()
        result = compliance.initialize()

        self.assertTrue(result)
        self.assertTrue(compliance._initialized)

    def test_default_controls_created(self):
        """Test default controls are created."""
        compliance = SOC2Compliance()
        compliance.initialize()

        controls = compliance.control_registry.get_all_controls()
        self.assertGreater(len(controls), 0)

    def test_default_risks_created(self):
        """Test default risks are created."""
        compliance = SOC2Compliance()
        compliance.initialize()

        risks = compliance.risk_registry._risks
        self.assertGreater(len(risks), 0)

    def test_get_compliance_report(self):
        """Test generating compliance report."""
        compliance = SOC2Compliance()
        compliance.initialize()

        report = compliance.get_compliance_report()

        self.assertEqual(report["organization"], "WarmLogic")
        self.assertIn("controls", report)
        self.assertIn("incidents", report)
        self.assertIn("risks", report)
        self.assertIn("audit_status", report)

    def test_audit_status_calculation(self):
        """Test audit status calculation."""
        compliance = SOC2Compliance()
        compliance.initialize()

        status = compliance._calculate_audit_status()

        self.assertIn("readiness_score", status)
        self.assertIn("status", status)


class TestGlobalFunctions(unittest.TestCase):
    """Test global SOC 2 functions."""

    def test_get_soc2_compliance(self):
        """Test getting global SOC 2 compliance instance."""
        compliance = get_soc2_compliance()
        self.assertIsNotNone(compliance)
        self.assertIsInstance(compliance, SOC2Compliance)

    def test_initialize_soc2(self):
        """Test initializing SOC 2 with custom org name."""
        compliance = initialize_soc2(organization_name="TestCorp")
        self.assertEqual(compliance.organization_name, "TestCorp")


if __name__ == "__main__":
    unittest.main()
