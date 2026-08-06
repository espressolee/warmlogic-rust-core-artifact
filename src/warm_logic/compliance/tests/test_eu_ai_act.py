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
[Q3 2026] EU AI Act Compliance Tests

Tests for EU AI Act compliance infrastructure including:
- AI System Registry
- Risk Assessment
- Technical Documentation
- Human Oversight
- Transparency
- Conformity Assessment
- Incident Management
"""

from __future__ import annotations

import unittest

from warm_logic.compliance.eu_ai_act import (
    AISystemRecord,
    AISystemRegistry,
    ConformityAssessment,
    ConformityAssessmentManager,
    ConformityStatus,
    EUAIActCompliance,
    HighRiskArea,
    HumanOversightManager,
    HumanOversightMeasure,
    IncidentManager,
    IncidentRecord,
    RiskAssessmentManager,
    RiskAssessmentRecord,
    RiskCategory,
    TechnicalDocumentation,
    TechnicalDocumentationManager,
    TransparencyManager,
    TransparencyRecord,
)

# =============================================================================
# AI System Registry Tests
# =============================================================================


class TestAISystemRegistry(unittest.TestCase):
    """Test AI system registry functionality."""

    def setUp(self):
        self.registry = AISystemRegistry()

    def test_register_system(self):
        """Test registering an AI system."""
        system = self.registry.register_system(
            name="WarmLogic Governance",
            description="AI governance system",
            provider="espressolee",
            intended_purpose="Autonomous AI governance",
        )

        self.assertIsInstance(system, AISystemRecord)
        self.assertEqual(system.name, "WarmLogic Governance")
        self.assertEqual(system.provider, "espressolee")
        self.assertIn(system.system_id, self.registry.systems)

    def test_update_risk_classification(self):
        """Test updating risk classification."""
        system = self.registry.register_system(
            name="Test System",
            description="Test",
            provider="Test Provider",
            intended_purpose="Testing",
        )

        result = self.registry.update_risk_classification(
            system_id=system.system_id,
            risk_category=RiskCategory.HIGH,
            high_risk_areas=[HighRiskArea.CRITICAL_INFRASTRUCTURE],
        )

        self.assertTrue(result)
        self.assertEqual(system.risk_category, RiskCategory.HIGH)
        self.assertIn(HighRiskArea.CRITICAL_INFRASTRUCTURE, system.high_risk_areas)

    def test_update_risk_classification_invalid(self):
        """Test updating non-existent system."""
        result = self.registry.update_risk_classification(
            system_id="invalid",
            risk_category=RiskCategory.HIGH,
        )
        self.assertFalse(result)

    def test_mark_registered_in_eu_database(self):
        """Test marking system as registered in EU database."""
        system = self.registry.register_system(
            name="Test",
            description="Test",
            provider="Provider",
            intended_purpose="Purpose",
        )

        result = self.registry.mark_registered_in_eu_database(system.system_id)
        self.assertTrue(result)
        self.assertTrue(system.eu_database_registered)

    def test_apply_ce_marking_high_risk(self):
        """Test applying CE marking to high-risk system."""
        system = self.registry.register_system(
            name="Test",
            description="Test",
            provider="Provider",
            intended_purpose="Purpose",
        )
        self.registry.update_risk_classification(
            system_id=system.system_id,
            risk_category=RiskCategory.HIGH,
        )

        result = self.registry.apply_ce_marking(system.system_id)
        self.assertTrue(result)
        self.assertTrue(system.ce_marking)

    def test_apply_ce_marking_non_high_risk(self):
        """Test CE marking not applicable to non-high-risk."""
        system = self.registry.register_system(
            name="Test",
            description="Test",
            provider="Provider",
            intended_purpose="Purpose",
        )

        result = self.registry.apply_ce_marking(system.system_id)
        self.assertFalse(result)

    def test_get_high_risk_systems(self):
        """Test getting high-risk systems."""
        system1 = self.registry.register_system(
            name="High Risk",
            description="Test",
            provider="Provider",
            intended_purpose="Purpose",
        )
        self.registry.update_risk_classification(
            system_id=system1.system_id,
            risk_category=RiskCategory.HIGH,
        )

        self.registry.register_system(
            name="Minimal Risk",
            description="Test",
            provider="Provider",
            intended_purpose="Purpose",
        )

        high_risk = self.registry.get_high_risk_systems()
        self.assertEqual(len(high_risk), 1)
        self.assertEqual(high_risk[0].name, "High Risk")

    def test_get_systems_by_area(self):
        """Test filtering systems by high-risk area."""
        system = self.registry.register_system(
            name="Employment AI",
            description="Test",
            provider="Provider",
            intended_purpose="Purpose",
        )
        self.registry.update_risk_classification(
            system_id=system.system_id,
            risk_category=RiskCategory.HIGH,
            high_risk_areas=[HighRiskArea.EMPLOYMENT],
        )

        systems = self.registry.get_systems_by_area(HighRiskArea.EMPLOYMENT)
        self.assertEqual(len(systems), 1)


# =============================================================================
# Risk Assessment Tests
# =============================================================================


class TestRiskAssessmentManager(unittest.TestCase):
    """Test risk assessment functionality."""

    def setUp(self):
        self.manager = RiskAssessmentManager()

    def test_conduct_assessment_minimal_risk(self):
        """Test assessment resulting in minimal risk."""
        assessment = self.manager.conduct_assessment(
            system_id="test-123",
            conducted_by="Security Team",
            intended_purpose="Internal analytics dashboard",
            use_cases=["data visualization", "reporting"],
        )

        self.assertIsInstance(assessment, RiskAssessmentRecord)
        self.assertEqual(assessment.risk_category, RiskCategory.MINIMAL)

    def test_conduct_assessment_high_risk(self):
        """Test assessment with high-risk areas."""
        assessment = self.manager.conduct_assessment(
            system_id="test-123",
            conducted_by="Security Team",
            intended_purpose="HR screening system",
            use_cases=["resume analysis", "candidate ranking"],
            high_risk_areas=[HighRiskArea.EMPLOYMENT],
        )

        self.assertEqual(assessment.risk_category, RiskCategory.HIGH)
        self.assertIn(HighRiskArea.EMPLOYMENT.value, assessment.high_risk_factors)

    def test_conduct_assessment_prohibited(self):
        """Test assessment detecting prohibited practice."""
        assessment = self.manager.conduct_assessment(
            system_id="test-123",
            conducted_by="Security Team",
            intended_purpose="subliminal manipulation system",
            use_cases=["hidden influence"],
        )

        self.assertEqual(assessment.risk_category, RiskCategory.UNACCEPTABLE)

    def test_conduct_assessment_limited_risk(self):
        """Test assessment for limited risk system."""
        assessment = self.manager.conduct_assessment(
            system_id="test-123",
            conducted_by="Security Team",
            intended_purpose="Customer service chatbot",
            use_cases=["chatbot interaction", "FAQ responses"],
        )

        self.assertEqual(assessment.risk_category, RiskCategory.LIMITED)

    def test_add_mitigation(self):
        """Test adding mitigation measure."""
        assessment = self.manager.conduct_assessment(
            system_id="test-123",
            conducted_by="Team",
            intended_purpose="Test",
            use_cases=[],
        )

        result = self.manager.add_mitigation(
            assessment_id=assessment.assessment_id,
            mitigation_measure="Implement access controls",
        )

        self.assertTrue(result)
        self.assertIn("Implement access controls", assessment.mitigation_measures)

    def test_get_assessments_for_system(self):
        """Test getting assessments for a specific system."""
        self.manager.conduct_assessment(
            system_id="system-1",
            conducted_by="Team",
            intended_purpose="Test",
            use_cases=[],
        )
        self.manager.conduct_assessment(
            system_id="system-1",
            conducted_by="Team",
            intended_purpose="Updated test",
            use_cases=[],
        )

        assessments = self.manager.get_assessments_for_system("system-1")
        self.assertEqual(len(assessments), 2)


# =============================================================================
# Technical Documentation Tests
# =============================================================================


class TestTechnicalDocumentationManager(unittest.TestCase):
    """Test technical documentation functionality."""

    def setUp(self):
        self.manager = TechnicalDocumentationManager()

    def test_create_documentation(self):
        """Test creating technical documentation."""
        doc = self.manager.create_documentation(
            system_id="test-123",
            version="1.0.0",
        )

        self.assertIsInstance(doc, TechnicalDocumentation)
        self.assertEqual(doc.system_id, "test-123")
        self.assertFalse(doc.is_complete)
        self.assertEqual(len(doc.missing_sections), len(self.manager.REQUIRED_SECTIONS))

    def test_update_section(self):
        """Test updating a documentation section."""
        doc = self.manager.create_documentation(system_id="test-123")
        initial_missing = len(doc.missing_sections)

        result = self.manager.update_section(
            doc_id=doc.doc_id,
            section="general_description",
            content="This is the general description.",
        )

        self.assertTrue(result)
        self.assertEqual(doc.general_description, "This is the general description.")
        self.assertEqual(len(doc.missing_sections), initial_missing - 1)

    def test_update_section_invalid(self):
        """Test updating non-existent documentation."""
        result = self.manager.update_section(
            doc_id="invalid",
            section="general_description",
            content="Test",
        )
        self.assertFalse(result)

    def test_update_accuracy_metrics(self):
        """Test updating accuracy metrics."""
        doc = self.manager.create_documentation(system_id="test-123")

        result = self.manager.update_accuracy_metrics(
            doc_id=doc.doc_id,
            metrics={"accuracy": 0.95, "f1_score": 0.92},
        )

        self.assertTrue(result)
        self.assertEqual(doc.accuracy_metrics["accuracy"], 0.95)

    def test_get_completeness_status(self):
        """Test getting completeness status."""
        doc = self.manager.create_documentation(system_id="test-123")
        self.manager.update_section(doc.doc_id, "general_description", "Content")

        status = self.manager.get_completeness_status(doc.doc_id)

        self.assertIn("completion_percentage", status)
        self.assertFalse(status["is_complete"])
        self.assertEqual(status["completed_sections"], 1)

    def test_documentation_completion(self):
        """Test documentation marked complete when all sections filled."""
        doc = self.manager.create_documentation(system_id="test-123")

        for section in self.manager.REQUIRED_SECTIONS:
            if section == "accuracy_metrics":
                self.manager.update_accuracy_metrics(doc.doc_id, {"test": 1})
            else:
                self.manager.update_section(doc.doc_id, section, "Content")

        self.assertTrue(doc.is_complete)
        self.assertEqual(len(doc.missing_sections), 0)


# =============================================================================
# Human Oversight Tests
# =============================================================================


class TestHumanOversightManager(unittest.TestCase):
    """Test human oversight functionality."""

    def setUp(self):
        self.manager = HumanOversightManager()

    def test_add_oversight_measure(self):
        """Test adding oversight measure."""
        measure = self.manager.add_oversight_measure(
            system_id="test-123",
            description="Manual review of all decisions",
            oversight_type="human-in-the-loop",
            responsible_party="Operations Team",
            has_stop_mechanism=True,
            has_intervention_capability=True,
        )

        self.assertIsInstance(measure, HumanOversightMeasure)
        self.assertTrue(measure.stop_mechanism)
        self.assertTrue(measure.intervention_capability)

    def test_update_implementation_status(self):
        """Test updating implementation status."""
        measure = self.manager.add_oversight_measure(
            system_id="test-123",
            description="Test measure",
            oversight_type="human-on-the-loop",
            responsible_party="Team",
        )

        result = self.manager.update_implementation_status(
            measure_id=measure.measure_id,
            status="implemented",
            interface_description="Dashboard interface",
        )

        self.assertTrue(result)
        self.assertEqual(measure.implementation_status, "implemented")

    def test_check_compliance_no_measures(self):
        """Test compliance check with no measures."""
        result = self.manager.check_compliance("nonexistent")

        self.assertFalse(result["compliant"])
        self.assertEqual(result["measures_count"], 0)

    def test_check_compliance_full(self):
        """Test compliance check with full measures."""
        measure = self.manager.add_oversight_measure(
            system_id="test-123",
            description="Full oversight",
            oversight_type="human-in-command",
            responsible_party="Team",
            has_stop_mechanism=True,
            has_intervention_capability=True,
        )
        self.manager.update_implementation_status(measure.measure_id, "implemented")

        result = self.manager.check_compliance("test-123")

        self.assertTrue(result["compliant"])
        self.assertTrue(result["has_stop_mechanism"])
        self.assertTrue(result["has_intervention_capability"])


# =============================================================================
# Transparency Tests
# =============================================================================


class TestTransparencyManager(unittest.TestCase):
    """Test transparency functionality."""

    def setUp(self):
        self.manager = TransparencyManager()

    def test_add_disclosure(self):
        """Test adding a disclosure."""
        record = self.manager.add_disclosure(
            system_id="test-123",
            disclosure_type="ai_interaction",
            disclosure_text="You are interacting with an AI system.",
            disclosure_mechanism="UI banner",
        )

        self.assertIsInstance(record, TransparencyRecord)
        self.assertFalse(record.verified)

    def test_verify_disclosure(self):
        """Test verifying a disclosure."""
        record = self.manager.add_disclosure(
            system_id="test-123",
            disclosure_type="ai_interaction",
            disclosure_text="Test",
            disclosure_mechanism="Test",
        )

        result = self.manager.verify_disclosure(record.record_id)

        self.assertTrue(result)
        self.assertTrue(record.verified)
        self.assertIsNotNone(record.implementation_date)

    def test_check_compliance_minimal_risk(self):
        """Test compliance check for minimal risk system."""
        result = self.manager.check_compliance("test-123", RiskCategory.MINIMAL)

        self.assertFalse(result["required"])

    def test_check_compliance_required(self):
        """Test compliance check for system requiring transparency."""
        record = self.manager.add_disclosure(
            system_id="test-123",
            disclosure_type="ai_interaction",
            disclosure_text="Test",
            disclosure_mechanism="Test",
        )
        self.manager.verify_disclosure(record.record_id)

        result = self.manager.check_compliance("test-123", RiskCategory.LIMITED)

        self.assertTrue(result["required"])
        self.assertTrue(result["compliant"])


# =============================================================================
# Conformity Assessment Tests
# =============================================================================


class TestConformityAssessmentManager(unittest.TestCase):
    """Test conformity assessment functionality."""

    def setUp(self):
        self.manager = ConformityAssessmentManager()

    def test_initiate_assessment(self):
        """Test initiating an assessment."""
        assessment = self.manager.initiate_assessment(
            system_id="test-123",
            assessment_type="internal",
        )

        self.assertIsInstance(assessment, ConformityAssessment)
        self.assertEqual(assessment.status, ConformityStatus.IN_PROGRESS)

    def test_add_finding(self):
        """Test adding a finding."""
        assessment = self.manager.initiate_assessment(
            system_id="test-123",
            assessment_type="internal",
        )

        result = self.manager.add_finding(
            assessment_id=assessment.assessment_id,
            finding="Documentation complete",
        )

        self.assertTrue(result)
        self.assertIn("Documentation complete", assessment.findings)

    def test_add_non_conformity(self):
        """Test adding a non-conformity."""
        assessment = self.manager.initiate_assessment(
            system_id="test-123",
            assessment_type="internal",
        )

        result = self.manager.add_non_conformity(
            assessment_id=assessment.assessment_id,
            non_conformity="Missing human oversight documentation",
            corrective_action="Update documentation with oversight procedures",
        )

        self.assertTrue(result)
        self.assertEqual(assessment.status, ConformityStatus.REQUIRES_REVIEW)
        self.assertEqual(len(assessment.non_conformities), 1)

    def test_complete_assessment_passed(self):
        """Test completing assessment with pass."""
        assessment = self.manager.initiate_assessment(
            system_id="test-123",
            assessment_type="internal",
        )

        result = self.manager.complete_assessment(
            assessment_id=assessment.assessment_id,
            passed=True,
            certificate_id="CERT-2026-001",
        )

        self.assertTrue(result)
        self.assertEqual(assessment.status, ConformityStatus.PASSED)
        self.assertEqual(assessment.certificate_id, "CERT-2026-001")
        self.assertIsNotNone(assessment.valid_until)

    def test_complete_assessment_failed(self):
        """Test completing assessment with fail."""
        assessment = self.manager.initiate_assessment(
            system_id="test-123",
            assessment_type="internal",
        )

        result = self.manager.complete_assessment(
            assessment_id=assessment.assessment_id,
            passed=False,
        )

        self.assertTrue(result)
        self.assertEqual(assessment.status, ConformityStatus.FAILED)


# =============================================================================
# Incident Manager Tests
# =============================================================================


class TestIncidentManager(unittest.TestCase):
    """Test incident management functionality."""

    def setUp(self):
        self.manager = IncidentManager()

    def test_report_incident(self):
        """Test reporting an incident."""
        incident = self.manager.report_incident(
            system_id="test-123",
            description="Unexpected system behavior",
            severity="high",
            fundamental_rights_impact=True,
            affected_parties=["User Group A"],
        )

        self.assertIsInstance(incident, IncidentRecord)
        self.assertEqual(incident.severity, "high")
        self.assertTrue(incident.fundamental_rights_impact)

    def test_notify_authority(self):
        """Test notifying authorities."""
        incident = self.manager.report_incident(
            system_id="test-123",
            description="Test incident",
        )

        result = self.manager.notify_authority(incident.incident_id)

        self.assertTrue(result)
        self.assertTrue(incident.notified_authority)
        self.assertIsNotNone(incident.reported_date)

    def test_resolve_incident(self):
        """Test resolving an incident."""
        incident = self.manager.report_incident(
            system_id="test-123",
            description="Test incident",
        )

        result = self.manager.resolve_incident(
            incident_id=incident.incident_id,
            root_cause="Configuration error",
            corrective_measures=["Updated configuration", "Added validation"],
        )

        self.assertTrue(result)
        self.assertEqual(incident.investigation_status, "resolved")
        self.assertEqual(incident.root_cause, "Configuration error")

    def test_get_open_incidents(self):
        """Test getting open incidents."""
        self.manager.report_incident(
            system_id="test-123",
            description="Open incident",
        )
        incident2 = self.manager.report_incident(
            system_id="test-456",
            description="Resolved incident",
        )
        self.manager.resolve_incident(incident2.incident_id, "Cause", [])

        open_incidents = self.manager.get_open_incidents()
        self.assertEqual(len(open_incidents), 1)


# =============================================================================
# EU AI Act Compliance Central Manager Tests
# =============================================================================


class TestEUAIActCompliance(unittest.TestCase):
    """Test central EU AI Act compliance manager."""

    def setUp(self):
        self.compliance = EUAIActCompliance(organization_name="Test Organization")

    def test_initialize(self):
        """Test compliance initialization."""
        result = self.compliance.initialize()
        self.assertTrue(result)

    def test_register_and_assess_system(self):
        """Test registering and assessing a system."""
        system, assessment = self.compliance.register_and_assess_system(
            name="Test AI System",
            description="A test system",
            intended_purpose="Testing functionality",
            provider="Test Provider",
            use_cases=["testing", "validation"],
        )

        self.assertIsInstance(system, AISystemRecord)
        self.assertIsInstance(assessment, RiskAssessmentRecord)
        self.assertEqual(system.risk_category, assessment.risk_category)

    def test_register_high_risk_system(self):
        """Test registering a high-risk system."""
        system, assessment = self.compliance.register_and_assess_system(
            name="Employment AI",
            description="HR screening system",
            intended_purpose="Candidate evaluation",
            provider="Provider",
            high_risk_areas=[HighRiskArea.EMPLOYMENT],
        )

        self.assertEqual(system.risk_category, RiskCategory.HIGH)
        self.assertEqual(assessment.risk_category, RiskCategory.HIGH)

    def test_get_compliance_report(self):
        """Test generating compliance report."""
        system, _ = self.compliance.register_and_assess_system(
            name="Test System",
            description="Test",
            intended_purpose="Testing",
            provider="Provider",
        )

        report = self.compliance.get_compliance_report(system.system_id)

        self.assertIn("system", report)
        self.assertIn("compliance_score", report)
        self.assertIn("human_oversight", report)
        self.assertIn("transparency", report)

    def test_get_compliance_report_not_found(self):
        """Test compliance report for non-existent system."""
        report = self.compliance.get_compliance_report("nonexistent")
        self.assertIn("error", report)

    def test_compliance_score_minimal_risk(self):
        """Test compliance score for minimal risk system."""
        system, _ = self.compliance.register_and_assess_system(
            name="Internal Tool",
            description="Internal analytics",
            intended_purpose="Internal reporting",
            provider="Provider",
        )

        report = self.compliance.get_compliance_report(system.system_id)
        self.assertEqual(report["compliance_score"], 100.0)

    def test_get_audit_checklist(self):
        """Test getting audit checklist."""
        system, _ = self.compliance.register_and_assess_system(
            name="Test System",
            description="Test",
            intended_purpose="Testing",
            provider="Provider",
        )

        checklist = self.compliance.get_audit_checklist(system.system_id)

        self.assertIsInstance(checklist, list)
        self.assertGreater(len(checklist), 0)
        self.assertIn("item", checklist[0])
        self.assertIn("article", checklist[0])

    def test_get_audit_checklist_high_risk(self):
        """Test audit checklist for high-risk system."""
        system, _ = self.compliance.register_and_assess_system(
            name="HR AI",
            description="Employment screening",
            intended_purpose="Candidate evaluation",
            provider="Provider",
            high_risk_areas=[HighRiskArea.EMPLOYMENT],
        )

        checklist = self.compliance.get_audit_checklist(system.system_id)

        # Should have more items for high-risk
        item_names = [item["item"] for item in checklist]
        self.assertIn("Human Oversight Measures", item_names)
        self.assertIn("Technical Documentation", item_names)

    def test_full_compliance_workflow(self):
        """Test full compliance workflow."""
        # 1. Register and assess
        system, _ = self.compliance.register_and_assess_system(
            name="High Risk AI",
            description="Employment system",
            intended_purpose="HR decisions",
            provider="Provider",
            high_risk_areas=[HighRiskArea.EMPLOYMENT],
        )

        # 2. Add human oversight
        measure = self.compliance.human_oversight.add_oversight_measure(
            system_id=system.system_id,
            description="Manual review",
            oversight_type="human-in-the-loop",
            responsible_party="HR Team",
            has_stop_mechanism=True,
            has_intervention_capability=True,
        )
        self.compliance.human_oversight.update_implementation_status(
            measure.measure_id, "implemented"
        )

        # 3. Add transparency disclosure
        disclosure = self.compliance.transparency.add_disclosure(
            system_id=system.system_id,
            disclosure_type="ai_interaction",
            disclosure_text="AI-assisted screening",
            disclosure_mechanism="UI notification",
        )
        self.compliance.transparency.verify_disclosure(disclosure.record_id)

        # 4. Create documentation
        doc = self.compliance.documentation.create_documentation(system.system_id)
        for section in self.compliance.documentation.REQUIRED_SECTIONS:
            if section == "accuracy_metrics":
                self.compliance.documentation.update_accuracy_metrics(
                    doc.doc_id, {"accuracy": 0.9}
                )
            else:
                self.compliance.documentation.update_section(
                    doc.doc_id, section, "Content"
                )

        # 5. Conduct conformity assessment
        assessment = self.compliance.conformity.initiate_assessment(
            system_id=system.system_id,
            assessment_type="internal",
        )
        self.compliance.conformity.complete_assessment(
            assessment.assessment_id,
            passed=True,
            certificate_id="CERT-001",
        )

        # 6. Apply CE marking
        self.compliance.registry.apply_ce_marking(system.system_id)

        # 7. Get final report
        report = self.compliance.get_compliance_report(system.system_id)

        self.assertGreater(report["compliance_score"], 80)
        self.assertTrue(report["system"]["ce_marking"])


if __name__ == "__main__":
    unittest.main()
