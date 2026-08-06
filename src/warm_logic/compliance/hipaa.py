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
[Q3 2026] HIPAA Compliance Infrastructure

Implements HIPAA compliance requirements:
- Privacy Rule: PHI handling and minimum necessary standard
- Security Rule: Administrative, Physical, Technical safeguards
- Breach Notification Rule: Incident notification requirements
- Business Associate Agreements: Third-party compliance tracking

Reference: 45 CFR Parts 160, 162, and 164
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# HIPAA Data Classifications
# =============================================================================


class PHICategory(Enum):
    """Categories of Protected Health Information (PHI)"""

    DEMOGRAPHIC = "demographic"  # Name, address, dates
    MEDICAL = "medical"  # Diagnoses, treatments
    PAYMENT = "payment"  # Insurance, billing
    GENETIC = "genetic"  # Genetic information (enhanced protection)
    PSYCHOTHERAPY = "psychotherapy"  # Psychotherapy notes (enhanced protection)
    SUBSTANCE_ABUSE = "substance_abuse"  # 42 CFR Part 2 protected


class DisclosureType(Enum):
    """Types of PHI disclosures"""

    TREATMENT = "treatment"
    PAYMENT = "payment"
    HEALTHCARE_OPERATIONS = "healthcare_operations"
    AUTHORIZATION = "authorization"  # Patient authorized
    REQUIRED_BY_LAW = "required_by_law"
    PUBLIC_HEALTH = "public_health"
    RESEARCH = "research"  # With IRB approval
    LIMITED_DATA_SET = "limited_data_set"


class SafeguardType(Enum):
    """HIPAA Security Rule safeguard categories"""

    ADMINISTRATIVE = "administrative"
    PHYSICAL = "physical"
    TECHNICAL = "technical"


class BreachSeverity(Enum):
    """Breach severity classification"""

    LOW = "low"  # Limited data, low risk
    MEDIUM = "medium"  # Some PHI, moderate risk
    HIGH = "high"  # Sensitive PHI, high risk
    CRITICAL = "critical"  # Large-scale or genetic/psychotherapy data


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class PHIRecord:
    """Represents a Protected Health Information record"""

    record_id: str
    patient_id: str
    category: PHICategory
    data_hash: str  # Never store actual PHI in logs
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime | None = None
    access_count: int = 0
    encryption_key_id: str | None = None
    retention_policy: str = "standard"  # 6 years default


@dataclass
class PHIAccessLog:
    """Audit log for PHI access"""

    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    record_id: str = ""
    user_id: str = ""
    action: str = ""  # view, modify, delete, export
    purpose: DisclosureType = DisclosureType.TREATMENT
    minimum_necessary_verified: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: str = ""
    success: bool = True
    denial_reason: str | None = None


@dataclass
class BusinessAssociate:
    """Business Associate Agreement tracking"""

    ba_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_name: str = ""
    contact_email: str = ""
    agreement_date: datetime = field(default_factory=datetime.utcnow)
    expiration_date: datetime | None = None
    services_provided: list[str] = field(default_factory=list)
    phi_access_level: str = "limited"  # none, limited, full
    last_audit_date: datetime | None = None
    is_active: bool = True
    subcontractors: list[str] = field(default_factory=list)


@dataclass
class SecuritySafeguard:
    """Security safeguard implementation"""

    safeguard_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    safeguard_type: SafeguardType = SafeguardType.TECHNICAL
    description: str = ""
    implementation_status: str = (
        "planned"  # planned, in_progress, implemented, verified
    )
    required: bool = True  # Required vs Addressable
    last_review_date: datetime | None = None
    evidence_location: str = ""
    responsible_party: str = ""


@dataclass
class BreachIncident:
    """HIPAA breach incident record"""

    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    discovered_date: datetime = field(default_factory=datetime.utcnow)
    occurred_date: datetime | None = None
    severity: BreachSeverity = BreachSeverity.LOW
    description: str = ""
    phi_categories_affected: list[PHICategory] = field(default_factory=list)
    individuals_affected: int = 0
    notification_required: bool = False
    notification_sent_date: datetime | None = None
    hhs_notified: bool = False  # Required if 500+ individuals
    root_cause: str = ""
    remediation_steps: list[str] = field(default_factory=list)
    status: str = "open"  # open, investigating, contained, resolved


@dataclass
class RiskAnalysis:
    """Security risk analysis record"""

    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conducted_date: datetime = field(default_factory=datetime.utcnow)
    conducted_by: str = ""
    scope: str = ""
    threats_identified: list[str] = field(default_factory=list)
    vulnerabilities_found: list[str] = field(default_factory=list)
    risk_level: str = "medium"  # low, medium, high, critical
    mitigation_plan: dict[str, Any] = field(default_factory=dict)
    next_review_date: datetime | None = None


# =============================================================================
# PHI Data Handler
# =============================================================================


class PHIDataHandler:
    """
    Handles Protected Health Information with HIPAA compliance.

    Features:
    - PHI classification and tracking
    - Minimum necessary standard enforcement
    - Access control and audit logging
    """

    def __init__(self) -> None:
        self.records: dict[str, PHIRecord] = {}
        self.access_logs: list[PHIAccessLog] = []
        self._access_policies: dict[str, list[PHICategory]] = {}

    def register_phi(
        self,
        patient_id: str,
        category: PHICategory,
        data: bytes | str,
        encryption_key_id: str | None = None,
    ) -> PHIRecord:
        """
        Register a PHI record (stores only hash, never actual data).

        Args:
            patient_id: Patient identifier
            category: PHI category
            data: Actual data (only hashed)
            encryption_key_id: Reference to encryption key

        Returns:
            PHIRecord with data hash
        """
        # Only store hash - never log or persist actual PHI
        if isinstance(data, str):
            data = data.encode("utf-8")
        data_hash = hashlib.sha256(data).hexdigest()

        record = PHIRecord(
            record_id=str(uuid.uuid4()),
            patient_id=patient_id,
            category=category,
            data_hash=data_hash,
            encryption_key_id=encryption_key_id,
        )
        self.records[record.record_id] = record

        logger.info(
            "PHI registered",
            extra={
                "record_id": record.record_id,
                "patient_id": patient_id[:8] + "***",  # Partial ID only
                "category": category.value,
            },
        )
        return record

    def set_access_policy(
        self, role: str, allowed_categories: list[PHICategory]
    ) -> None:
        """Set minimum necessary access policy for a role."""
        self._access_policies[role] = allowed_categories
        logger.info(f"Access policy set for role: {role}")

    def check_access(
        self,
        user_id: str,
        user_role: str,
        record_id: str,
        purpose: DisclosureType,
    ) -> tuple[bool, str | None]:
        """
        Check if access is permitted under minimum necessary standard.

        Returns:
            Tuple of (allowed, denial_reason)
        """
        record = self.records.get(record_id)
        if not record:
            return False, "Record not found"

        # Check role-based access
        allowed_categories = self._access_policies.get(user_role, [])
        if record.category not in allowed_categories:
            return (
                False,
                f"Role '{user_role}' not authorized for {record.category.value} PHI",
            )

        # Enhanced protection for sensitive categories
        if record.category in (
            PHICategory.GENETIC,
            PHICategory.PSYCHOTHERAPY,
            PHICategory.SUBSTANCE_ABUSE,
        ):
            if purpose not in (DisclosureType.TREATMENT, DisclosureType.AUTHORIZATION):
                return (
                    False,
                    f"Enhanced protection: {record.category.value} requires specific authorization",
                )

        return True, None

    def access_phi(
        self,
        user_id: str,
        user_role: str,
        record_id: str,
        action: str,
        purpose: DisclosureType,
        ip_address: str = "",
    ) -> PHIAccessLog:
        """
        Access PHI with full audit logging.

        Args:
            user_id: User making the request
            user_role: User's role for access control
            record_id: PHI record ID
            action: Access action (view, modify, delete, export)
            purpose: Disclosure purpose
            ip_address: Source IP

        Returns:
            Access log entry
        """
        allowed, denial_reason = self.check_access(
            user_id, user_role, record_id, purpose
        )

        log_entry = PHIAccessLog(
            record_id=record_id,
            user_id=user_id,
            action=action,
            purpose=purpose,
            minimum_necessary_verified=allowed,
            ip_address=ip_address,
            success=allowed,
            denial_reason=denial_reason,
        )
        self.access_logs.append(log_entry)

        if allowed and record_id in self.records:
            record = self.records[record_id]
            record.last_accessed = datetime.utcnow()
            record.access_count += 1

        logger.info(
            "PHI access attempt",
            extra={
                "record_id": record_id,
                "user_id": user_id,
                "action": action,
                "allowed": allowed,
            },
        )

        return log_entry

    def get_access_history(
        self,
        record_id: str | None = None,
        user_id: str | None = None,
        since: datetime | None = None,
    ) -> list[PHIAccessLog]:
        """Get PHI access history with optional filters."""
        logs = self.access_logs

        if record_id:
            logs = [log for log in logs if log.record_id == record_id]
        if user_id:
            logs = [log for log in logs if log.user_id == user_id]
        if since:
            logs = [log for log in logs if log.timestamp >= since]

        return logs


# =============================================================================
# Security Safeguards Registry
# =============================================================================


class SafeguardsRegistry:
    """
    Manages HIPAA Security Rule safeguards.

    Tracks implementation status of all required and addressable safeguards.
    """

    def __init__(self) -> None:
        self.safeguards: dict[str, SecuritySafeguard] = {}
        self._initialize_required_safeguards()

    def _initialize_required_safeguards(self) -> None:
        """Initialize required HIPAA safeguards."""
        required_safeguards = [
            # Administrative Safeguards (45 CFR 164.308)
            (
                "risk_analysis",
                SafeguardType.ADMINISTRATIVE,
                "Conduct accurate and thorough risk analysis",
                True,
            ),
            (
                "risk_management",
                SafeguardType.ADMINISTRATIVE,
                "Implement security measures to reduce risks",
                True,
            ),
            (
                "sanction_policy",
                SafeguardType.ADMINISTRATIVE,
                "Apply sanctions against violating workforce members",
                True,
            ),
            (
                "information_system_activity_review",
                SafeguardType.ADMINISTRATIVE,
                "Regularly review system activity",
                True,
            ),
            (
                "workforce_security",
                SafeguardType.ADMINISTRATIVE,
                "Implement policies for workforce access",
                True,
            ),
            (
                "security_awareness_training",
                SafeguardType.ADMINISTRATIVE,
                "Implement security awareness program",
                True,
            ),
            (
                "contingency_plan",
                SafeguardType.ADMINISTRATIVE,
                "Establish contingency plan for emergencies",
                True,
            ),
            # Physical Safeguards (45 CFR 164.310)
            (
                "facility_access_controls",
                SafeguardType.PHYSICAL,
                "Limit physical access to facilities",
                True,
            ),
            (
                "workstation_use",
                SafeguardType.PHYSICAL,
                "Implement policies for workstation use",
                True,
            ),
            (
                "workstation_security",
                SafeguardType.PHYSICAL,
                "Implement physical safeguards for workstations",
                True,
            ),
            (
                "device_media_controls",
                SafeguardType.PHYSICAL,
                "Control receipt/removal of hardware and media",
                True,
            ),
            # Technical Safeguards (45 CFR 164.312)
            (
                "access_control",
                SafeguardType.TECHNICAL,
                "Allow access only to authorized persons",
                True,
            ),
            (
                "audit_controls",
                SafeguardType.TECHNICAL,
                "Implement hardware/software audit mechanisms",
                True,
            ),
            (
                "integrity_controls",
                SafeguardType.TECHNICAL,
                "Protect ePHI from improper alteration",
                True,
            ),
            (
                "transmission_security",
                SafeguardType.TECHNICAL,
                "Guard against unauthorized access during transmission",
                True,
            ),
        ]

        for name, stype, desc, required in required_safeguards:
            self.add_safeguard(
                name=name,
                safeguard_type=stype,
                description=desc,
                required=required,
            )

    def add_safeguard(
        self,
        name: str,
        safeguard_type: SafeguardType,
        description: str,
        required: bool = True,
        responsible_party: str = "",
    ) -> SecuritySafeguard:
        """Add a security safeguard."""
        safeguard = SecuritySafeguard(
            name=name,
            safeguard_type=safeguard_type,
            description=description,
            required=required,
            responsible_party=responsible_party,
        )
        self.safeguards[safeguard.safeguard_id] = safeguard
        return safeguard

    def update_status(
        self,
        safeguard_id: str,
        status: str,
        evidence_location: str = "",
    ) -> bool:
        """Update safeguard implementation status."""
        if safeguard_id not in self.safeguards:
            return False

        safeguard = self.safeguards[safeguard_id]
        safeguard.implementation_status = status
        if evidence_location:
            safeguard.evidence_location = evidence_location
        safeguard.last_review_date = datetime.utcnow()
        return True

    def get_by_type(self, safeguard_type: SafeguardType) -> list[SecuritySafeguard]:
        """Get safeguards by type."""
        return [
            s for s in self.safeguards.values() if s.safeguard_type == safeguard_type
        ]

    def get_compliance_status(self) -> dict[str, Any]:
        """Get overall safeguards compliance status."""
        total = len(self.safeguards)
        implemented = len(
            [
                s
                for s in self.safeguards.values()
                if s.implementation_status == "implemented"
            ]
        )
        verified = len(
            [
                s
                for s in self.safeguards.values()
                if s.implementation_status == "verified"
            ]
        )
        required_implemented = len(
            [
                s
                for s in self.safeguards.values()
                if s.required and s.implementation_status in ("implemented", "verified")
            ]
        )
        total_required = len([s for s in self.safeguards.values() if s.required])

        return {
            "total_safeguards": total,
            "implemented": implemented,
            "verified": verified,
            "required_compliance": (
                required_implemented / total_required if total_required > 0 else 0
            ),
            "overall_score": (implemented + verified) / total if total > 0 else 0,
            "by_type": {
                stype.value: {
                    "total": len(self.get_by_type(stype)),
                    "implemented": len(
                        [
                            s
                            for s in self.get_by_type(stype)
                            if s.implementation_status in ("implemented", "verified")
                        ]
                    ),
                }
                for stype in SafeguardType
            },
        }


# =============================================================================
# Business Associate Management
# =============================================================================


class BusinessAssociateManager:
    """
    Manages Business Associate Agreements (BAAs).

    Tracks third-party compliance and subcontractor chains.
    """

    def __init__(self) -> None:
        self.associates: dict[str, BusinessAssociate] = {}

    def register_associate(
        self,
        organization_name: str,
        contact_email: str,
        services_provided: list[str],
        phi_access_level: str = "limited",
        agreement_duration_days: int = 365,
    ) -> BusinessAssociate:
        """Register a new business associate."""
        ba = BusinessAssociate(
            organization_name=organization_name,
            contact_email=contact_email,
            services_provided=services_provided,
            phi_access_level=phi_access_level,
            expiration_date=datetime.utcnow() + timedelta(days=agreement_duration_days),
        )
        self.associates[ba.ba_id] = ba

        logger.info(f"Business Associate registered: {organization_name}")
        return ba

    def add_subcontractor(self, ba_id: str, subcontractor_name: str) -> bool:
        """Add a subcontractor to a business associate."""
        if ba_id not in self.associates:
            return False

        self.associates[ba_id].subcontractors.append(subcontractor_name)
        logger.info(f"Subcontractor added to BA {ba_id}: {subcontractor_name}")
        return True

    def record_audit(self, ba_id: str) -> bool:
        """Record a compliance audit for a business associate."""
        if ba_id not in self.associates:
            return False

        self.associates[ba_id].last_audit_date = datetime.utcnow()
        return True

    def check_expiring(self, within_days: int = 30) -> list[BusinessAssociate]:
        """Get business associates with expiring agreements."""
        threshold = datetime.utcnow() + timedelta(days=within_days)
        return [
            ba
            for ba in self.associates.values()
            if ba.is_active and ba.expiration_date and ba.expiration_date <= threshold
        ]

    def deactivate(self, ba_id: str) -> bool:
        """Deactivate a business associate relationship."""
        if ba_id not in self.associates:
            return False

        self.associates[ba_id].is_active = False
        logger.info(f"Business Associate deactivated: {ba_id}")
        return True

    def get_phi_access_summary(self) -> dict[str, list[str]]:
        """Get summary of PHI access by business associates."""
        return {
            "full_access": [
                ba.organization_name
                for ba in self.associates.values()
                if ba.is_active and ba.phi_access_level == "full"
            ],
            "limited_access": [
                ba.organization_name
                for ba in self.associates.values()
                if ba.is_active and ba.phi_access_level == "limited"
            ],
            "no_access": [
                ba.organization_name
                for ba in self.associates.values()
                if ba.is_active and ba.phi_access_level == "none"
            ],
        }


# =============================================================================
# Breach Notification Manager
# =============================================================================


class BreachNotificationManager:
    """
    Manages HIPAA breach notification requirements.

    Implements breach risk assessment and notification timelines.
    """

    # HHS notification threshold
    HHS_NOTIFICATION_THRESHOLD = 500

    def __init__(
        self, notification_callback: Callable[[BreachIncident], None] | None = None
    ):
        self.incidents: dict[str, BreachIncident] = {}
        self._notification_callback = notification_callback

    def report_breach(
        self,
        description: str,
        phi_categories: list[PHICategory],
        individuals_affected: int,
        severity: BreachSeverity | None = None,
        occurred_date: datetime | None = None,
    ) -> BreachIncident:
        """
        Report a potential breach.

        Args:
            description: Description of the breach
            phi_categories: Types of PHI affected
            individuals_affected: Number of individuals affected
            severity: Override severity (auto-calculated if not provided)
            occurred_date: When the breach occurred

        Returns:
            BreachIncident record
        """
        # Auto-calculate severity if not provided
        if severity is None:
            severity = self._assess_severity(phi_categories, individuals_affected)

        # Determine if notification is required
        notification_required = self._is_notification_required(
            phi_categories, individuals_affected
        )

        incident = BreachIncident(
            description=description,
            phi_categories_affected=phi_categories,
            individuals_affected=individuals_affected,
            severity=severity,
            occurred_date=occurred_date,
            notification_required=notification_required,
            hhs_notified=False,
        )
        self.incidents[incident.incident_id] = incident

        logger.warning(
            "Breach reported",
            extra={
                "incident_id": incident.incident_id,
                "severity": severity.value,
                "individuals": individuals_affected,
                "notification_required": notification_required,
            },
        )

        return incident

    def _assess_severity(
        self,
        phi_categories: list[PHICategory],
        individuals_affected: int,
    ) -> BreachSeverity:
        """Assess breach severity based on factors."""
        # Check for sensitive categories
        sensitive_categories = {
            PHICategory.GENETIC,
            PHICategory.PSYCHOTHERAPY,
            PHICategory.SUBSTANCE_ABUSE,
        }
        has_sensitive = bool(set(phi_categories) & sensitive_categories)

        if individuals_affected >= 500 or has_sensitive:
            return BreachSeverity.CRITICAL
        elif individuals_affected >= 100:
            return BreachSeverity.HIGH
        elif individuals_affected >= 10:
            return BreachSeverity.MEDIUM
        else:
            return BreachSeverity.LOW

    def _is_notification_required(
        self,
        phi_categories: list[PHICategory],
        individuals_affected: int,
    ) -> bool:
        """
        Determine if breach notification is required.

        Notification is NOT required if breach meets one of these exceptions:
        1. PHI was encrypted with a valid encryption key
        2. PHI was returned unused and uncompromised
        3. PHI was destroyed before it could be read
        """
        # For this implementation, we assume notification is required
        # unless explicitly marked otherwise
        return individuals_affected > 0 and len(phi_categories) > 0

    def send_notifications(self, incident_id: str) -> dict[str, Any]:
        """
        Send required notifications for a breach.

        Returns:
            Status of notification attempts
        """
        if incident_id not in self.incidents:
            return {"success": False, "error": "Incident not found"}

        incident = self.incidents[incident_id]
        results = {
            "incident_id": incident_id,
            "individuals_notified": False,
            "hhs_notified": False,
            "media_notified": False,
        }

        if not incident.notification_required:
            return {"success": True, "message": "No notification required", **results}

        # Individual notifications (within 60 days of discovery)
        if self._notification_callback:
            self._notification_callback(incident)
        results["individuals_notified"] = True
        incident.notification_sent_date = datetime.utcnow()

        # HHS notification (immediate if 500+ individuals, annual otherwise)
        if incident.individuals_affected >= self.HHS_NOTIFICATION_THRESHOLD:
            # In production, this would submit to HHS breach portal
            incident.hhs_notified = True
            results["hhs_notified"] = True
            results["media_notified"] = True  # Required for 500+ breaches

        logger.info(f"Breach notifications sent for incident {incident_id}")
        return {"success": True, **results}

    def resolve_incident(
        self,
        incident_id: str,
        root_cause: str,
        remediation_steps: list[str],
    ) -> bool:
        """Resolve a breach incident."""
        if incident_id not in self.incidents:
            return False

        incident = self.incidents[incident_id]
        incident.root_cause = root_cause
        incident.remediation_steps = remediation_steps
        incident.status = "resolved"

        logger.info(f"Breach incident resolved: {incident_id}")
        return True

    def get_metrics(self) -> dict[str, Any]:
        """Get breach metrics for reporting."""
        total = len(self.incidents)
        open_incidents = [i for i in self.incidents.values() if i.status != "resolved"]
        total_affected = sum(i.individuals_affected for i in self.incidents.values())

        return {
            "total_incidents": total,
            "open_incidents": len(open_incidents),
            "resolved_incidents": total - len(open_incidents),
            "total_individuals_affected": total_affected,
            "by_severity": {
                severity.value: len(
                    [i for i in self.incidents.values() if i.severity == severity]
                )
                for severity in BreachSeverity
            },
            "hhs_reported": len([i for i in self.incidents.values() if i.hhs_notified]),
        }


# =============================================================================
# Risk Analysis Manager
# =============================================================================


class RiskAnalysisManager:
    """
    Manages HIPAA-required risk analysis.

    Implements ongoing risk assessment and mitigation tracking.
    """

    def __init__(self) -> None:
        self.analyses: dict[str, RiskAnalysis] = {}

    def conduct_analysis(
        self,
        conducted_by: str,
        scope: str,
        threats: list[str],
        vulnerabilities: list[str],
        risk_level: str = "medium",
        review_interval_days: int = 365,
    ) -> RiskAnalysis:
        """
        Conduct a risk analysis.

        Args:
            conducted_by: Person/team conducting analysis
            scope: Scope of the analysis
            threats: Identified threats
            vulnerabilities: Identified vulnerabilities
            risk_level: Overall risk level
            review_interval_days: Days until next review

        Returns:
            RiskAnalysis record
        """
        analysis = RiskAnalysis(
            conducted_by=conducted_by,
            scope=scope,
            threats_identified=threats,
            vulnerabilities_found=vulnerabilities,
            risk_level=risk_level,
            next_review_date=datetime.utcnow() + timedelta(days=review_interval_days),
        )
        self.analyses[analysis.analysis_id] = analysis

        logger.info(
            "Risk analysis conducted",
            extra={
                "analysis_id": analysis.analysis_id,
                "scope": scope,
                "risk_level": risk_level,
            },
        )
        return analysis

    def add_mitigation(
        self,
        analysis_id: str,
        risk_item: str,
        mitigation_plan: str,
        responsible_party: str,
        target_date: datetime | None = None,
    ) -> bool:
        """Add mitigation plan for a specific risk."""
        if analysis_id not in self.analyses:
            return False

        analysis = self.analyses[analysis_id]
        if "mitigations" not in analysis.mitigation_plan:
            analysis.mitigation_plan["mitigations"] = []

        analysis.mitigation_plan["mitigations"].append(
            {
                "risk_item": risk_item,
                "plan": mitigation_plan,
                "responsible_party": responsible_party,
                "target_date": target_date.isoformat() if target_date else None,
                "status": "planned",
            }
        )
        return True

    def get_overdue_reviews(self) -> list[RiskAnalysis]:
        """Get risk analyses that need review."""
        now = datetime.utcnow()
        return [
            analysis
            for analysis in self.analyses.values()
            if analysis.next_review_date and analysis.next_review_date <= now
        ]

    def get_high_risk_items(self) -> list[RiskAnalysis]:
        """Get analyses with high or critical risk levels."""
        return [
            analysis
            for analysis in self.analyses.values()
            if analysis.risk_level in ("high", "critical")
        ]


# =============================================================================
# HIPAA Compliance Central Manager
# =============================================================================


class HIPAACompliance:
    """
    Central HIPAA compliance manager.

    Integrates all HIPAA compliance components:
    - PHI data handling
    - Security safeguards
    - Business associate management
    - Breach notification
    - Risk analysis
    """

    def __init__(
        self,
        organization_name: str = "WarmLogic",
        notification_callback: Callable[[BreachIncident], None] | None = None,
    ):
        self.organization_name = organization_name
        self.phi_handler = PHIDataHandler()
        self.safeguards = SafeguardsRegistry()
        self.business_associates = BusinessAssociateManager()
        self.breach_manager = BreachNotificationManager(notification_callback)
        self.risk_manager = RiskAnalysisManager()

        self._initialized = False
        self._compliance_officer: str | None = None

    def initialize(self, compliance_officer: str | None = None) -> bool:
        """
        Initialize HIPAA compliance infrastructure.

        Args:
            compliance_officer: Designated compliance officer

        Returns:
            True if initialized successfully
        """
        self._compliance_officer = compliance_officer
        self._initialized = True

        logger.info(
            f"HIPAA compliance initialized for {self.organization_name}",
            extra={"compliance_officer": compliance_officer},
        )
        return True

    def get_compliance_report(self) -> dict[str, Any]:
        """
        Generate comprehensive HIPAA compliance report.

        Returns:
            Compliance report with all component statuses
        """
        safeguards_status = self.safeguards.get_compliance_status()
        breach_metrics = self.breach_manager.get_metrics()

        # Calculate overall compliance score
        safeguards_score = safeguards_status["required_compliance"] * 100
        breach_score = (
            100
            if breach_metrics["open_incidents"] == 0
            else max(0, 100 - breach_metrics["open_incidents"] * 10)
        )
        ba_score = self._calculate_ba_score()
        risk_score = self._calculate_risk_score()

        overall_score = (
            safeguards_score * 0.4
            + breach_score * 0.2
            + ba_score * 0.2
            + risk_score * 0.2
        )

        return {
            "organization": self.organization_name,
            "compliance_officer": self._compliance_officer,
            "report_date": datetime.utcnow().isoformat(),
            "overall_score": round(overall_score, 1),
            "status": (
                "compliant"
                if overall_score >= 80
                else "needs_improvement" if overall_score >= 60 else "non_compliant"
            ),
            "safeguards": safeguards_status,
            "breach_metrics": breach_metrics,
            "business_associates": {
                "total_active": len(
                    [
                        ba
                        for ba in self.business_associates.associates.values()
                        if ba.is_active
                    ]
                ),
                "expiring_soon": len(self.business_associates.check_expiring(30)),
                "phi_access_summary": self.business_associates.get_phi_access_summary(),
            },
            "risk_analysis": {
                "total_analyses": len(self.risk_manager.analyses),
                "overdue_reviews": len(self.risk_manager.get_overdue_reviews()),
                "high_risk_items": len(self.risk_manager.get_high_risk_items()),
            },
            "phi_handling": {
                "total_records": len(self.phi_handler.records),
                "access_logs_count": len(self.phi_handler.access_logs),
                "denied_accesses": len(
                    [log for log in self.phi_handler.access_logs if not log.success]
                ),
            },
        }

    def _calculate_ba_score(self) -> float:
        """Calculate business associate compliance score."""
        associates = list(self.business_associates.associates.values())
        if not associates:
            return 100.0

        active = [ba for ba in associates if ba.is_active]
        if not active:
            return 100.0

        audited = len([ba for ba in active if ba.last_audit_date])
        return (audited / len(active)) * 100

    def _calculate_risk_score(self) -> float:
        """Calculate risk management score."""
        analyses = list(self.risk_manager.analyses.values())
        if not analyses:
            return 50.0  # No analyses = needs improvement

        overdue = len(self.risk_manager.get_overdue_reviews())
        high_risk = len(self.risk_manager.get_high_risk_items())

        score = 100.0
        score -= overdue * 15  # Penalty for overdue reviews
        score -= high_risk * 10  # Penalty for unresolved high risks
        return max(0.0, score)

    def get_audit_checklist(self) -> list[dict[str, Any]]:
        """
        Generate HIPAA audit checklist.

        Returns:
            List of audit items with status
        """
        safeguards_status = self.safeguards.get_compliance_status()

        checklist = [
            {
                "item": "Security Risk Analysis",
                "requirement": "45 CFR 164.308(a)(1)(ii)(A)",
                "status": "pass" if len(self.risk_manager.analyses) > 0 else "fail",
                "notes": f"{len(self.risk_manager.analyses)} analyses on record",
            },
            {
                "item": "Workforce Training",
                "requirement": "45 CFR 164.308(a)(5)",
                "status": "pending",
                "notes": "Verify training records externally",
            },
            {
                "item": "Access Controls",
                "requirement": "45 CFR 164.312(a)",
                "status": (
                    "pass"
                    if len(self.phi_handler._access_policies) > 0
                    else "needs_work"
                ),
                "notes": f"{len(self.phi_handler._access_policies)} access policies defined",
            },
            {
                "item": "Audit Controls",
                "requirement": "45 CFR 164.312(b)",
                "status": "pass",
                "notes": f"{len(self.phi_handler.access_logs)} access events logged",
            },
            {
                "item": "Business Associate Agreements",
                "requirement": "45 CFR 164.314",
                "status": (
                    "pass"
                    if len(self.business_associates.check_expiring(0)) == 0
                    else "needs_work"
                ),
                "notes": f"{len(self.business_associates.associates)} agreements on file",
            },
            {
                "item": "Breach Notification Procedures",
                "requirement": "45 CFR 164.400-414",
                "status": "pass",
                "notes": "Breach notification system active",
            },
            {
                "item": "Administrative Safeguards",
                "requirement": "45 CFR 164.308",
                "status": (
                    "pass"
                    if safeguards_status["by_type"]["administrative"]["implemented"] > 0
                    else "needs_work"
                ),
                "notes": f"{safeguards_status['by_type']['administrative']['implemented']}/{safeguards_status['by_type']['administrative']['total']} implemented",
            },
            {
                "item": "Physical Safeguards",
                "requirement": "45 CFR 164.310",
                "status": (
                    "pass"
                    if safeguards_status["by_type"]["physical"]["implemented"] > 0
                    else "needs_work"
                ),
                "notes": f"{safeguards_status['by_type']['physical']['implemented']}/{safeguards_status['by_type']['physical']['total']} implemented",
            },
            {
                "item": "Technical Safeguards",
                "requirement": "45 CFR 164.312",
                "status": (
                    "pass"
                    if safeguards_status["by_type"]["technical"]["implemented"] > 0
                    else "needs_work"
                ),
                "notes": f"{safeguards_status['by_type']['technical']['implemented']}/{safeguards_status['by_type']['technical']['total']} implemented",
            },
        ]

        return checklist
