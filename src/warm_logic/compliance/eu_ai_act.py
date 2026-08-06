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
[Q3 2026] EU AI Act Compliance Infrastructure

Implements EU AI Act (Regulation (EU) 2024/1689) compliance requirements:
- Risk Classification (Article 6, Annex III)
- High-Risk AI Requirements (Chapter 2, Articles 8-15)
- Transparency Obligations (Article 50)
- Human Oversight (Article 14)
- Technical Documentation (Annex IV)
- Conformity Assessment (Article 43)

Reference: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# EU AI Act Classifications
# =============================================================================


class RiskCategory(Enum):
    """AI System Risk Categories (Article 6)"""

    UNACCEPTABLE = "unacceptable"  # Prohibited (Article 5)
    HIGH = "high"  # High-risk (Annex III)
    LIMITED = "limited"  # Limited transparency obligations
    MINIMAL = "minimal"  # No specific requirements


class HighRiskArea(Enum):
    """High-Risk AI Areas (Annex III)"""

    BIOMETRIC = "biometric"  # Biometric identification
    CRITICAL_INFRASTRUCTURE = (
        "critical_infrastructure"  # Management of critical infrastructure
    )
    EDUCATION = "education"  # Educational/vocational training
    EMPLOYMENT = "employment"  # Employment, worker management
    ESSENTIAL_SERVICES = "essential_services"  # Access to essential services
    LAW_ENFORCEMENT = "law_enforcement"  # Law enforcement
    MIGRATION = "migration"  # Migration, asylum, border control
    JUSTICE = "justice"  # Administration of justice


class ConformityStatus(Enum):
    """Conformity Assessment Status"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


class TransparencyLevel(Enum):
    """Transparency Obligation Level"""

    NONE = "none"
    BASIC = "basic"  # Limited risk systems
    FULL = "full"  # High-risk systems


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AISystemRecord:
    """Record of an AI system subject to EU AI Act"""

    system_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    provider: str = ""  # AI system provider
    deployer: str = ""  # Entity deploying the system
    risk_category: RiskCategory = RiskCategory.MINIMAL
    high_risk_areas: list[HighRiskArea] = field(default_factory=list)
    intended_purpose: str = ""
    registration_date: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    eu_database_registered: bool = False
    ce_marking: bool = False


@dataclass
class RiskAssessmentRecord:
    """Risk assessment for AI system classification"""

    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_id: str = ""
    conducted_by: str = ""
    conducted_date: datetime = field(default_factory=datetime.utcnow)
    risk_category: RiskCategory = RiskCategory.MINIMAL
    assessment_rationale: str = ""
    high_risk_factors: list[str] = field(default_factory=list)
    mitigation_measures: list[str] = field(default_factory=list)
    next_review_date: datetime | None = None


@dataclass
class TechnicalDocumentation:
    """Technical documentation (Annex IV)"""

    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_id: str = ""
    version: str = "1.0.0"
    created_date: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    # Annex IV required elements
    general_description: str = ""
    detailed_description: str = ""
    development_process: str = ""
    monitoring_functioning: str = ""
    risk_management: str = ""
    data_governance: str = ""
    accuracy_metrics: dict[str, Any] = field(default_factory=dict)
    cybersecurity_measures: str = ""
    human_oversight_description: str = ""

    # Completeness tracking
    is_complete: bool = False
    missing_sections: list[str] = field(default_factory=list)


@dataclass
class HumanOversightMeasure:
    """Human oversight measures (Article 14)"""

    measure_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_id: str = ""
    description: str = ""
    oversight_type: str = ""  # human-in-the-loop, human-on-the-loop, human-in-command
    responsible_party: str = ""
    implementation_status: str = "planned"
    interface_description: str = ""
    stop_mechanism: bool = False  # Ability to stop AI system
    intervention_capability: bool = False  # Ability to intervene


@dataclass
class TransparencyRecord:
    """Transparency compliance record (Article 50)"""

    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_id: str = ""
    disclosure_type: str = ""  # ai_interaction, synthetic_content, emotion_recognition
    disclosure_text: str = ""
    disclosure_mechanism: str = ""
    implementation_date: datetime | None = None
    verified: bool = False


@dataclass
class ConformityAssessment:
    """Conformity assessment record (Article 43)"""

    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_id: str = ""
    assessment_type: str = ""  # internal, notified_body
    notified_body_id: str | None = None
    conducted_date: datetime = field(default_factory=datetime.utcnow)
    status: ConformityStatus = ConformityStatus.NOT_STARTED
    findings: list[str] = field(default_factory=list)
    non_conformities: list[str] = field(default_factory=list)
    corrective_actions: list[str] = field(default_factory=list)
    certificate_id: str | None = None
    valid_until: datetime | None = None


@dataclass
class IncidentRecord:
    """Serious incident record (Article 73)"""

    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_id: str = ""
    occurred_date: datetime = field(default_factory=datetime.utcnow)
    reported_date: datetime | None = None
    description: str = ""
    severity: str = "medium"  # low, medium, high, critical
    affected_parties: list[str] = field(default_factory=list)
    fundamental_rights_impact: bool = False
    health_safety_impact: bool = False
    notified_authority: bool = False
    investigation_status: str = "open"
    root_cause: str = ""
    corrective_measures: list[str] = field(default_factory=list)


# =============================================================================
# AI System Registry
# =============================================================================


class AISystemRegistry:
    """
    Registry for AI systems subject to EU AI Act.

    Tracks system registrations and their risk classifications.
    """

    def __init__(self) -> None:
        self.systems: dict[str, AISystemRecord] = {}

    def register_system(
        self,
        name: str,
        description: str,
        provider: str,
        intended_purpose: str,
        version: str = "1.0.0",
        deployer: str = "",
    ) -> AISystemRecord:
        """
        Register an AI system.

        Args:
            name: System name
            description: System description
            provider: AI provider organization
            intended_purpose: Intended purpose of the system
            version: System version
            deployer: Entity deploying the system

        Returns:
            AISystemRecord
        """
        system = AISystemRecord(
            name=name,
            description=description,
            provider=provider,
            deployer=deployer,
            intended_purpose=intended_purpose,
            version=version,
        )
        self.systems[system.system_id] = system

        logger.info(f"AI system registered: {name} (ID: {system.system_id})")
        return system

    def update_risk_classification(
        self,
        system_id: str,
        risk_category: RiskCategory,
        high_risk_areas: list[HighRiskArea] | None = None,
    ) -> bool:
        """Update risk classification for a system."""
        if system_id not in self.systems:
            return False

        system = self.systems[system_id]
        system.risk_category = risk_category
        if high_risk_areas:
            system.high_risk_areas = high_risk_areas
        system.last_updated = datetime.utcnow()

        logger.info(
            f"Risk classification updated for {system_id}: {risk_category.value}"
        )
        return True

    def mark_registered_in_eu_database(self, system_id: str) -> bool:
        """Mark system as registered in EU AI database."""
        if system_id not in self.systems:
            return False

        self.systems[system_id].eu_database_registered = True
        self.systems[system_id].last_updated = datetime.utcnow()
        return True

    def apply_ce_marking(self, system_id: str) -> bool:
        """Apply CE marking to a system."""
        if system_id not in self.systems:
            return False

        system = self.systems[system_id]
        # CE marking only for high-risk systems that have passed conformity
        if system.risk_category != RiskCategory.HIGH:
            return False

        system.ce_marking = True
        system.last_updated = datetime.utcnow()
        return True

    def get_high_risk_systems(self) -> list[AISystemRecord]:
        """Get all high-risk AI systems."""
        return [
            s for s in self.systems.values() if s.risk_category == RiskCategory.HIGH
        ]

    def get_systems_by_area(self, area: HighRiskArea) -> list[AISystemRecord]:
        """Get systems by high-risk area."""
        return [s for s in self.systems.values() if area in s.high_risk_areas]


# =============================================================================
# Risk Assessment Manager
# =============================================================================


class RiskAssessmentManager:
    """
    Manages risk assessments for AI systems (Article 6).

    Determines risk classification based on intended purpose and use case.
    """

    # Prohibited practices keywords (Article 5)
    PROHIBITED_KEYWORDS = [
        "subliminal",
        "manipulative",
        "social_scoring",
        "real_time_biometric_public",
        "predictive_policing_individual",
    ]

    def __init__(self) -> None:
        self.assessments: dict[str, RiskAssessmentRecord] = {}

    def conduct_assessment(
        self,
        system_id: str,
        conducted_by: str,
        intended_purpose: str,
        use_cases: list[str],
        high_risk_areas: list[HighRiskArea] | None = None,
    ) -> RiskAssessmentRecord:
        """
        Conduct risk assessment for an AI system.

        Args:
            system_id: AI system ID
            conducted_by: Person conducting assessment
            intended_purpose: System's intended purpose
            use_cases: List of use cases
            high_risk_areas: Applicable high-risk areas

        Returns:
            RiskAssessmentRecord
        """
        # Determine risk category
        risk_category, rationale, factors = self._assess_risk(
            intended_purpose, use_cases, high_risk_areas
        )

        assessment = RiskAssessmentRecord(
            system_id=system_id,
            conducted_by=conducted_by,
            risk_category=risk_category,
            assessment_rationale=rationale,
            high_risk_factors=factors,
            next_review_date=datetime.utcnow() + timedelta(days=365),
        )
        self.assessments[assessment.assessment_id] = assessment

        logger.info(
            f"Risk assessment conducted for {system_id}: {risk_category.value}",
            extra={"assessment_id": assessment.assessment_id},
        )
        return assessment

    def _assess_risk(
        self,
        intended_purpose: str,
        use_cases: list[str],
        high_risk_areas: list[HighRiskArea] | None,
    ) -> tuple[RiskCategory, str, list[str]]:
        """
        Assess risk category based on inputs.

        Returns:
            Tuple of (risk_category, rationale, high_risk_factors)
        """
        purpose_lower = intended_purpose.lower()
        use_cases_lower = [uc.lower() for uc in use_cases]
        all_text = purpose_lower + " " + " ".join(use_cases_lower)

        high_risk_factors = []

        # Check for prohibited practices
        for keyword in self.PROHIBITED_KEYWORDS:
            if keyword in all_text:
                return (
                    RiskCategory.UNACCEPTABLE,
                    f"Prohibited practice detected: {keyword}",
                    [keyword],
                )

        # Check for high-risk areas
        if high_risk_areas:
            high_risk_factors.extend([area.value for area in high_risk_areas])
            return (
                RiskCategory.HIGH,
                f"System operates in high-risk area(s): {', '.join(high_risk_factors)}",
                high_risk_factors,
            )

        # Check for limited risk indicators (transparency obligations)
        limited_risk_keywords = [
            "chatbot",
            "emotion_recognition",
            "deepfake",
            "synthetic",
            "generated_content",
        ]
        for keyword in limited_risk_keywords:
            if keyword in all_text:
                return (
                    RiskCategory.LIMITED,
                    f"Limited risk - transparency obligation for: {keyword}",
                    [keyword],
                )

        # Default to minimal risk
        return (
            RiskCategory.MINIMAL,
            "No high-risk indicators identified",
            [],
        )

    def add_mitigation(
        self,
        assessment_id: str,
        mitigation_measure: str,
    ) -> bool:
        """Add mitigation measure to assessment."""
        if assessment_id not in self.assessments:
            return False

        self.assessments[assessment_id].mitigation_measures.append(mitigation_measure)
        return True

    def get_assessments_for_system(self, system_id: str) -> list[RiskAssessmentRecord]:
        """Get all assessments for a system."""
        return [a for a in self.assessments.values() if a.system_id == system_id]


# =============================================================================
# Technical Documentation Manager
# =============================================================================


class TechnicalDocumentationManager:
    """
    Manages technical documentation (Annex IV).

    Ensures required documentation is complete and up-to-date.
    """

    REQUIRED_SECTIONS = [
        "general_description",
        "detailed_description",
        "development_process",
        "monitoring_functioning",
        "risk_management",
        "data_governance",
        "accuracy_metrics",
        "cybersecurity_measures",
        "human_oversight_description",
    ]

    def __init__(self) -> None:
        self.documentation: dict[str, TechnicalDocumentation] = {}

    def create_documentation(
        self,
        system_id: str,
        version: str = "1.0.0",
    ) -> TechnicalDocumentation:
        """Create technical documentation record for a system."""
        doc = TechnicalDocumentation(
            system_id=system_id,
            version=version,
        )
        doc.missing_sections = self.REQUIRED_SECTIONS.copy()
        self.documentation[doc.doc_id] = doc

        logger.info(f"Technical documentation created for system {system_id}")
        return doc

    def update_section(
        self,
        doc_id: str,
        section: str,
        content: str,
    ) -> bool:
        """Update a documentation section."""
        if doc_id not in self.documentation:
            return False

        doc = self.documentation[doc_id]
        if not hasattr(doc, section):
            return False

        setattr(doc, section, content)
        doc.last_updated = datetime.utcnow()

        # Update missing sections
        if section in doc.missing_sections:
            doc.missing_sections.remove(section)

        # Check completeness
        doc.is_complete = len(doc.missing_sections) == 0

        return True

    def update_accuracy_metrics(
        self,
        doc_id: str,
        metrics: dict[str, Any],
    ) -> bool:
        """Update accuracy metrics."""
        if doc_id not in self.documentation:
            return False

        doc = self.documentation[doc_id]
        doc.accuracy_metrics.update(metrics)
        doc.last_updated = datetime.utcnow()

        if "accuracy_metrics" in doc.missing_sections:
            doc.missing_sections.remove("accuracy_metrics")
        doc.is_complete = len(doc.missing_sections) == 0

        return True

    def get_completeness_status(self, doc_id: str) -> dict[str, Any]:
        """Get documentation completeness status."""
        if doc_id not in self.documentation:
            return {"error": "Documentation not found"}

        doc = self.documentation[doc_id]
        total_sections = len(self.REQUIRED_SECTIONS)
        completed_sections = total_sections - len(doc.missing_sections)

        return {
            "doc_id": doc_id,
            "is_complete": doc.is_complete,
            "completion_percentage": (completed_sections / total_sections) * 100,
            "completed_sections": completed_sections,
            "total_sections": total_sections,
            "missing_sections": doc.missing_sections,
        }


# =============================================================================
# Human Oversight Manager
# =============================================================================


class HumanOversightManager:
    """
    Manages human oversight measures (Article 14).

    Ensures appropriate human control over high-risk AI systems.
    """

    def __init__(self) -> None:
        self.measures: dict[str, HumanOversightMeasure] = {}

    def add_oversight_measure(
        self,
        system_id: str,
        description: str,
        oversight_type: str,
        responsible_party: str,
        has_stop_mechanism: bool = False,
        has_intervention_capability: bool = False,
    ) -> HumanOversightMeasure:
        """
        Add a human oversight measure.

        Args:
            system_id: AI system ID
            description: Description of the oversight measure
            oversight_type: Type of oversight (human-in-the-loop, human-on-the-loop, human-in-command)
            responsible_party: Person/role responsible
            has_stop_mechanism: Whether system can be stopped
            has_intervention_capability: Whether human can intervene

        Returns:
            HumanOversightMeasure
        """
        measure = HumanOversightMeasure(
            system_id=system_id,
            description=description,
            oversight_type=oversight_type,
            responsible_party=responsible_party,
            stop_mechanism=has_stop_mechanism,
            intervention_capability=has_intervention_capability,
        )
        self.measures[measure.measure_id] = measure

        logger.info(f"Human oversight measure added for {system_id}")
        return measure

    def update_implementation_status(
        self,
        measure_id: str,
        status: str,
        interface_description: str = "",
    ) -> bool:
        """Update implementation status of oversight measure."""
        if measure_id not in self.measures:
            return False

        measure = self.measures[measure_id]
        measure.implementation_status = status
        if interface_description:
            measure.interface_description = interface_description
        return True

    def get_measures_for_system(self, system_id: str) -> list[HumanOversightMeasure]:
        """Get all oversight measures for a system."""
        return [m for m in self.measures.values() if m.system_id == system_id]

    def check_compliance(self, system_id: str) -> dict[str, Any]:
        """Check human oversight compliance for a system."""
        measures = self.get_measures_for_system(system_id)

        if not measures:
            return {
                "system_id": system_id,
                "compliant": False,
                "reason": "No human oversight measures defined",
                "measures_count": 0,
            }

        has_stop = any(m.stop_mechanism for m in measures)
        has_intervention = any(m.intervention_capability for m in measures)
        all_implemented = all(
            m.implementation_status == "implemented" for m in measures
        )

        compliant = has_stop and has_intervention and all_implemented

        return {
            "system_id": system_id,
            "compliant": compliant,
            "measures_count": len(measures),
            "has_stop_mechanism": has_stop,
            "has_intervention_capability": has_intervention,
            "all_implemented": all_implemented,
        }


# =============================================================================
# Transparency Manager
# =============================================================================


class TransparencyManager:
    """
    Manages transparency obligations (Article 50).

    Ensures users are informed when interacting with AI systems.
    """

    DISCLOSURE_TYPES = [
        "ai_interaction",  # User interacting with AI
        "synthetic_content",  # AI-generated content
        "emotion_recognition",  # Emotion recognition system
        "biometric_categorization",  # Biometric categorization
    ]

    def __init__(self) -> None:
        self.records: dict[str, TransparencyRecord] = {}

    def add_disclosure(
        self,
        system_id: str,
        disclosure_type: str,
        disclosure_text: str,
        disclosure_mechanism: str,
    ) -> TransparencyRecord:
        """
        Add a transparency disclosure.

        Args:
            system_id: AI system ID
            disclosure_type: Type of disclosure required
            disclosure_text: The actual disclosure text
            disclosure_mechanism: How disclosure is presented (UI, audio, etc.)

        Returns:
            TransparencyRecord
        """
        record = TransparencyRecord(
            system_id=system_id,
            disclosure_type=disclosure_type,
            disclosure_text=disclosure_text,
            disclosure_mechanism=disclosure_mechanism,
        )
        self.records[record.record_id] = record

        logger.info(f"Transparency disclosure added for {system_id}: {disclosure_type}")
        return record

    def verify_disclosure(self, record_id: str) -> bool:
        """Mark a disclosure as verified."""
        if record_id not in self.records:
            return False

        record = self.records[record_id]
        record.verified = True
        record.implementation_date = datetime.utcnow()
        return True

    def get_disclosures_for_system(self, system_id: str) -> list[TransparencyRecord]:
        """Get all disclosures for a system."""
        return [r for r in self.records.values() if r.system_id == system_id]

    def check_compliance(
        self, system_id: str, risk_category: RiskCategory
    ) -> dict[str, Any]:
        """Check transparency compliance."""
        disclosures = self.get_disclosures_for_system(system_id)

        if risk_category == RiskCategory.MINIMAL:
            return {
                "system_id": system_id,
                "required": False,
                "reason": "Minimal risk - no transparency obligations",
            }

        if not disclosures:
            return {
                "system_id": system_id,
                "required": True,
                "compliant": False,
                "reason": "No disclosures defined",
            }

        all_verified = all(d.verified for d in disclosures)

        return {
            "system_id": system_id,
            "required": True,
            "compliant": all_verified,
            "disclosures_count": len(disclosures),
            "verified_count": sum(1 for d in disclosures if d.verified),
        }


# =============================================================================
# Conformity Assessment Manager
# =============================================================================


class ConformityAssessmentManager:
    """
    Manages conformity assessments (Article 43).

    Tracks assessment status for high-risk AI systems.
    """

    def __init__(self) -> None:
        self.assessments: dict[str, ConformityAssessment] = {}

    def initiate_assessment(
        self,
        system_id: str,
        assessment_type: str = "internal",
        notified_body_id: str | None = None,
    ) -> ConformityAssessment:
        """
        Initiate a conformity assessment.

        Args:
            system_id: AI system ID
            assessment_type: internal or notified_body
            notified_body_id: ID of notified body (if applicable)

        Returns:
            ConformityAssessment
        """
        assessment = ConformityAssessment(
            system_id=system_id,
            assessment_type=assessment_type,
            notified_body_id=notified_body_id,
            status=ConformityStatus.IN_PROGRESS,
        )
        self.assessments[assessment.assessment_id] = assessment

        logger.info(f"Conformity assessment initiated for {system_id}")
        return assessment

    def add_finding(self, assessment_id: str, finding: str) -> bool:
        """Add a finding to the assessment."""
        if assessment_id not in self.assessments:
            return False

        self.assessments[assessment_id].findings.append(finding)
        return True

    def add_non_conformity(
        self,
        assessment_id: str,
        non_conformity: str,
        corrective_action: str,
    ) -> bool:
        """Add a non-conformity with corrective action."""
        if assessment_id not in self.assessments:
            return False

        assessment = self.assessments[assessment_id]
        assessment.non_conformities.append(non_conformity)
        assessment.corrective_actions.append(corrective_action)
        assessment.status = ConformityStatus.REQUIRES_REVIEW
        return True

    def complete_assessment(
        self,
        assessment_id: str,
        passed: bool,
        certificate_id: str | None = None,
        valid_years: int = 5,
    ) -> bool:
        """Complete the assessment."""
        if assessment_id not in self.assessments:
            return False

        assessment = self.assessments[assessment_id]
        assessment.status = (
            ConformityStatus.PASSED if passed else ConformityStatus.FAILED
        )

        if passed and certificate_id:
            assessment.certificate_id = certificate_id
            assessment.valid_until = datetime.utcnow() + timedelta(
                days=365 * valid_years
            )

        logger.info(
            f"Conformity assessment completed for {assessment.system_id}: "
            f"{'PASSED' if passed else 'FAILED'}"
        )
        return True

    def get_assessment_for_system(self, system_id: str) -> ConformityAssessment | None:
        """Get latest assessment for a system."""
        assessments = [a for a in self.assessments.values() if a.system_id == system_id]
        if not assessments:
            return None
        return max(assessments, key=lambda a: a.conducted_date)


# =============================================================================
# Incident Manager
# =============================================================================


class IncidentManager:
    """
    Manages serious incident reporting (Article 73).

    Tracks and reports incidents affecting fundamental rights or safety.
    """

    def __init__(self) -> None:
        self.incidents: dict[str, IncidentRecord] = {}

    def report_incident(
        self,
        system_id: str,
        description: str,
        severity: str = "medium",
        fundamental_rights_impact: bool = False,
        health_safety_impact: bool = False,
        affected_parties: list[str] | None = None,
    ) -> IncidentRecord:
        """
        Report a serious incident.

        Args:
            system_id: AI system ID
            description: Incident description
            severity: Severity level
            fundamental_rights_impact: Impact on fundamental rights
            health_safety_impact: Impact on health or safety
            affected_parties: List of affected parties

        Returns:
            IncidentRecord
        """
        incident = IncidentRecord(
            system_id=system_id,
            description=description,
            severity=severity,
            fundamental_rights_impact=fundamental_rights_impact,
            health_safety_impact=health_safety_impact,
            affected_parties=affected_parties or [],
        )
        self.incidents[incident.incident_id] = incident

        logger.warning(
            f"Serious incident reported for {system_id}",
            extra={
                "incident_id": incident.incident_id,
                "severity": severity,
            },
        )
        return incident

    def notify_authority(self, incident_id: str) -> bool:
        """Mark incident as notified to authorities."""
        if incident_id not in self.incidents:
            return False

        incident = self.incidents[incident_id]
        incident.notified_authority = True
        incident.reported_date = datetime.utcnow()
        return True

    def resolve_incident(
        self,
        incident_id: str,
        root_cause: str,
        corrective_measures: list[str],
    ) -> bool:
        """Resolve an incident."""
        if incident_id not in self.incidents:
            return False

        incident = self.incidents[incident_id]
        incident.root_cause = root_cause
        incident.corrective_measures = corrective_measures
        incident.investigation_status = "resolved"
        return True

    def get_incidents_for_system(self, system_id: str) -> list[IncidentRecord]:
        """Get all incidents for a system."""
        return [i for i in self.incidents.values() if i.system_id == system_id]

    def get_open_incidents(self) -> list[IncidentRecord]:
        """Get all open incidents."""
        return [i for i in self.incidents.values() if i.investigation_status == "open"]


# =============================================================================
# EU AI Act Compliance Central Manager
# =============================================================================


class EUAIActCompliance:
    """
    Central EU AI Act compliance manager.

    Integrates all compliance components:
    - AI System Registry
    - Risk Assessment
    - Technical Documentation
    - Human Oversight
    - Transparency
    - Conformity Assessment
    - Incident Management
    """

    def __init__(self, organization_name: str = "WarmLogic"):
        self.organization_name = organization_name
        self.registry = AISystemRegistry()
        self.risk_assessor = RiskAssessmentManager()
        self.documentation = TechnicalDocumentationManager()
        self.human_oversight = HumanOversightManager()
        self.transparency = TransparencyManager()
        self.conformity = ConformityAssessmentManager()
        self.incidents = IncidentManager()

        self._initialized = False

    def initialize(self) -> bool:
        """Initialize EU AI Act compliance infrastructure."""
        self._initialized = True
        logger.info(f"EU AI Act compliance initialized for {self.organization_name}")
        return True

    def register_and_assess_system(
        self,
        name: str,
        description: str,
        intended_purpose: str,
        provider: str,
        deployer: str = "",
        use_cases: list[str] | None = None,
        high_risk_areas: list[HighRiskArea] | None = None,
    ) -> tuple[AISystemRecord, RiskAssessmentRecord]:
        """
        Register a system and conduct risk assessment.

        Returns:
            Tuple of (AISystemRecord, RiskAssessmentRecord)
        """
        # Register system
        system = self.registry.register_system(
            name=name,
            description=description,
            provider=provider,
            deployer=deployer,
            intended_purpose=intended_purpose,
        )

        # Conduct risk assessment
        assessment = self.risk_assessor.conduct_assessment(
            system_id=system.system_id,
            conducted_by=provider,
            intended_purpose=intended_purpose,
            use_cases=use_cases or [],
            high_risk_areas=high_risk_areas,
        )

        # Update system with risk classification
        self.registry.update_risk_classification(
            system_id=system.system_id,
            risk_category=assessment.risk_category,
            high_risk_areas=high_risk_areas,
        )

        return system, assessment

    def get_compliance_report(self, system_id: str) -> dict[str, Any]:
        """
        Generate compliance report for a specific AI system.

        Args:
            system_id: AI system ID

        Returns:
            Comprehensive compliance report
        """
        system = self.registry.systems.get(system_id)
        if not system:
            return {"error": "System not found"}

        # Get related records
        assessments = self.risk_assessor.get_assessments_for_system(system_id)
        oversight_status = self.human_oversight.check_compliance(system_id)
        transparency_status = self.transparency.check_compliance(
            system_id, system.risk_category
        )
        conformity = self.conformity.get_assessment_for_system(system_id)
        incidents = self.incidents.get_incidents_for_system(system_id)

        # Get documentation status
        doc_status = None
        for doc in self.documentation.documentation.values():
            if doc.system_id == system_id:
                doc_status = self.documentation.get_completeness_status(doc.doc_id)
                break

        # Calculate overall compliance score
        score = self._calculate_compliance_score(
            system=system,
            oversight_status=oversight_status,
            transparency_status=transparency_status,
            conformity=conformity,
            doc_status=doc_status,
        )

        return {
            "system": {
                "id": system.system_id,
                "name": system.name,
                "risk_category": system.risk_category.value,
                "high_risk_areas": [a.value for a in system.high_risk_areas],
                "ce_marking": system.ce_marking,
                "eu_database_registered": system.eu_database_registered,
            },
            "compliance_score": score,
            "risk_assessments": len(assessments),
            "human_oversight": oversight_status,
            "transparency": transparency_status,
            "conformity_assessment": (
                {
                    "status": conformity.status.value,
                    "certificate_id": conformity.certificate_id,
                }
                if conformity
                else None
            ),
            "documentation": doc_status,
            "incidents": {
                "total": len(incidents),
                "open": len([i for i in incidents if i.investigation_status == "open"]),
            },
            "report_date": datetime.utcnow().isoformat(),
        }

    def _calculate_compliance_score(
        self,
        system: AISystemRecord,
        oversight_status: dict[str, Any],
        transparency_status: dict[str, Any],
        conformity: ConformityAssessment | None,
        doc_status: dict[str, Any] | None,
    ) -> float:
        """Calculate overall compliance score."""
        if system.risk_category == RiskCategory.MINIMAL:
            return 100.0  # Minimal risk = fully compliant

        if system.risk_category == RiskCategory.UNACCEPTABLE:
            return 0.0  # Prohibited = non-compliant

        score = 0.0
        weight_total = 0.0

        # Human oversight (25%)
        if oversight_status.get("compliant"):
            score += 25.0
        weight_total += 25.0

        # Transparency (20%)
        if transparency_status.get("compliant") or not transparency_status.get(
            "required"
        ):
            score += 20.0
        weight_total += 20.0

        # Conformity assessment (30%)
        if conformity and conformity.status == ConformityStatus.PASSED:
            score += 30.0
        weight_total += 30.0

        # Documentation (25%)
        if doc_status and doc_status.get("is_complete"):
            score += 25.0
        elif doc_status:
            score += doc_status.get("completion_percentage", 0) * 0.25
        weight_total += 25.0

        return round((score / weight_total) * 100, 1) if weight_total > 0 else 0.0

    def get_audit_checklist(self, system_id: str) -> list[dict[str, Any]]:
        """
        Generate EU AI Act audit checklist for a system.

        Returns:
            List of audit items with status
        """
        system = self.registry.systems.get(system_id)
        if not system:
            return []

        checklist = [
            {
                "item": "System Registration",
                "article": "Article 49",
                "status": "pass" if system.system_id else "fail",
                "notes": f"Registered as {system.system_id}",
            },
            {
                "item": "Risk Classification",
                "article": "Article 6",
                "status": "pass",
                "notes": f"Classified as {system.risk_category.value} risk",
            },
        ]

        if system.risk_category == RiskCategory.HIGH:
            # High-risk system requirements
            oversight = self.human_oversight.check_compliance(system_id)
            checklist.extend(
                [
                    {
                        "item": "Human Oversight Measures",
                        "article": "Article 14",
                        "status": (
                            "pass" if oversight.get("compliant") else "needs_work"
                        ),
                        "notes": f"{oversight.get('measures_count', 0)} measures defined",
                    },
                    {
                        "item": "Technical Documentation",
                        "article": "Annex IV",
                        "status": "pending",
                        "notes": "Verify documentation completeness",
                    },
                    {
                        "item": "Conformity Assessment",
                        "article": "Article 43",
                        "status": "pass" if system.ce_marking else "needs_work",
                        "notes": "CE marking required for market placement",
                    },
                    {
                        "item": "EU Database Registration",
                        "article": "Article 71",
                        "status": (
                            "pass" if system.eu_database_registered else "needs_work"
                        ),
                        "notes": "Registration in EU database required",
                    },
                ]
            )

        transparency = self.transparency.check_compliance(
            system_id, system.risk_category
        )
        if transparency.get("required"):
            checklist.append(
                {
                    "item": "Transparency Obligations",
                    "article": "Article 50",
                    "status": "pass" if transparency.get("compliant") else "needs_work",
                    "notes": f"{transparency.get('verified_count', 0)}/{transparency.get('disclosures_count', 0)} verified",
                }
            )

        return checklist
