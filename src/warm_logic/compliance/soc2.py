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
[Q3 2026] SOC 2 Type I/II Compliance Infrastructure

Implements SOC 2 Trust Service Criteria:
- Security (CC): Common Criteria
- Availability (A): System availability commitments
- Processing Integrity (PI): Data processing accuracy
- Confidentiality (C): Information protection
- Privacy (P): Personal information handling

Based on AICPA Trust Service Criteria (2017).
"""

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SOC2")


class TrustServiceCategory(Enum):
    """SOC 2 Trust Service Categories."""

    SECURITY = "security"  # CC: Common Criteria
    AVAILABILITY = "availability"  # A: System availability
    PROCESSING_INTEGRITY = "processing_integrity"  # PI: Accurate processing
    CONFIDENTIALITY = "confidentiality"  # C: Information protection
    PRIVACY = "privacy"  # P: Personal information


class ControlStatus(Enum):
    """Status of a security control."""

    IMPLEMENTED = "implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"


class RiskLevel(Enum):
    """Risk assessment levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class IncidentSeverity(Enum):
    """Security incident severity levels."""

    SEV1 = "sev1"  # Critical: System down, data breach
    SEV2 = "sev2"  # High: Major functionality impacted
    SEV3 = "sev3"  # Medium: Minor functionality impacted
    SEV4 = "sev4"  # Low: Minimal impact


class IncidentStatus(Enum):
    """Security incident status."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class SecurityControl:
    """SOC 2 Security Control definition."""

    control_id: str
    category: TrustServiceCategory
    title: str
    description: str
    status: ControlStatus = ControlStatus.NOT_IMPLEMENTED
    implementation_notes: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    owner: str = ""
    last_reviewed: Optional[float] = None
    review_frequency_days: int = 90

    @property
    def needs_review(self) -> bool:
        """Check if control needs review."""
        if self.last_reviewed is None:
            return True
        days_since = (time.time() - self.last_reviewed) / (24 * 60 * 60)
        return days_since >= self.review_frequency_days

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "control_id": self.control_id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "implementation_notes": self.implementation_notes,
            "evidence_refs": self.evidence_refs,
            "owner": self.owner,
            "needs_review": self.needs_review,
        }


@dataclass
class AccessLog:
    """Access control audit log entry."""

    log_id: str
    timestamp: float
    user_id: str
    action: str  # login, logout, access, modify, delete
    resource: str
    resource_type: str
    success: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "log_id": self.log_id,
            "timestamp": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "resource_type": self.resource_type,
            "success": self.success,
            "ip_address": self.ip_address,
        }


@dataclass
class ChangeRecord:
    """Change management record."""

    change_id: str
    title: str
    description: str
    change_type: str  # standard, emergency, normal
    requester: str
    approver: Optional[str] = None
    status: str = "pending"  # pending, approved, rejected, implemented, rolled_back
    created_at: float = field(default_factory=time.time)
    approved_at: Optional[float] = None
    implemented_at: Optional[float] = None
    affected_systems: List[str] = field(default_factory=list)
    rollback_plan: str = ""
    test_results: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "change_id": self.change_id,
            "title": self.title,
            "change_type": self.change_type,
            "requester": self.requester,
            "approver": self.approver,
            "status": self.status,
            "created_at": datetime.fromtimestamp(
                self.created_at, tz=timezone.utc
            ).isoformat(),
            "affected_systems": self.affected_systems,
        }


@dataclass
class SecurityIncident:
    """Security incident record."""

    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    reported_by: str = ""
    assigned_to: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    detected_at: Optional[float] = None
    mitigated_at: Optional[float] = None
    resolved_at: Optional[float] = None
    affected_systems: List[str] = field(default_factory=list)
    root_cause: Optional[str] = None
    remediation_steps: List[str] = field(default_factory=list)
    lessons_learned: Optional[str] = None

    @property
    def time_to_detect(self) -> Optional[float]:
        """Time from creation to detection (hours)."""
        if self.detected_at and self.created_at:
            return (self.detected_at - self.created_at) / 3600
        return None

    @property
    def time_to_mitigate(self) -> Optional[float]:
        """Time from detection to mitigation (hours)."""
        if self.mitigated_at and self.detected_at:
            return (self.mitigated_at - self.detected_at) / 3600
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "severity": self.severity.value,
            "status": self.status.value,
            "reported_by": self.reported_by,
            "assigned_to": self.assigned_to,
            "created_at": datetime.fromtimestamp(
                self.created_at, tz=timezone.utc
            ).isoformat(),
            "affected_systems": self.affected_systems,
            "time_to_detect_hours": self.time_to_detect,
            "time_to_mitigate_hours": self.time_to_mitigate,
        }


@dataclass
class RiskAssessment:
    """Risk assessment record."""

    risk_id: str
    title: str
    description: str
    category: TrustServiceCategory
    likelihood: RiskLevel
    impact: RiskLevel
    inherent_risk: RiskLevel = RiskLevel.MEDIUM
    residual_risk: RiskLevel = RiskLevel.LOW
    controls: List[str] = field(default_factory=list)  # Control IDs
    owner: str = ""
    status: str = "open"  # open, mitigated, accepted, closed
    created_at: float = field(default_factory=time.time)
    last_assessed: Optional[float] = None
    mitigation_plan: str = ""

    def calculate_risk_score(self) -> int:
        """Calculate risk score (1-25)."""
        likelihood_scores = {
            RiskLevel.CRITICAL: 5,
            RiskLevel.HIGH: 4,
            RiskLevel.MEDIUM: 3,
            RiskLevel.LOW: 2,
            RiskLevel.INFORMATIONAL: 1,
        }
        return likelihood_scores[self.likelihood] * likelihood_scores[self.impact]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "risk_id": self.risk_id,
            "title": self.title,
            "category": self.category.value,
            "likelihood": self.likelihood.value,
            "impact": self.impact.value,
            "inherent_risk": self.inherent_risk.value,
            "residual_risk": self.residual_risk.value,
            "risk_score": self.calculate_risk_score(),
            "controls": self.controls,
            "status": self.status,
        }


class ControlRegistry:
    """
    [Q3 2026] Security Control Registry

    Manages SOC 2 security controls and their implementation status.
    """

    def __init__(self) -> None:
        self._controls: Dict[str, SecurityControl] = {}
        self._lock = threading.Lock()

    def register_control(self, control: SecurityControl) -> None:
        """Register a security control."""
        with self._lock:
            self._controls[control.control_id] = control
        logger.info(f"Control registered: {control.control_id} - {control.title}")

    def get_control(self, control_id: str) -> Optional[SecurityControl]:
        """Get a control by ID."""
        return self._controls.get(control_id)

    def get_controls_by_category(
        self, category: TrustServiceCategory
    ) -> List[SecurityControl]:
        """Get all controls in a category."""
        return [c for c in self._controls.values() if c.category == category]

    def get_all_controls(self) -> List[SecurityControl]:
        """Get all registered controls."""
        return list(self._controls.values())

    def update_status(
        self,
        control_id: str,
        status: ControlStatus,
        notes: str = "",
    ) -> bool:
        """Update control implementation status."""
        control = self._controls.get(control_id)
        if not control:
            return False

        with self._lock:
            control.status = status
            if notes:
                control.implementation_notes = notes
            control.last_reviewed = time.time()
        return True

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get compliance summary by category."""
        summary: Dict[str, Dict[str, int]] = {}

        for category in TrustServiceCategory:
            controls = self.get_controls_by_category(category)
            summary[category.value] = {
                "total": len(controls),
                "implemented": len(
                    [c for c in controls if c.status == ControlStatus.IMPLEMENTED]
                ),
                "partial": len(
                    [
                        c
                        for c in controls
                        if c.status == ControlStatus.PARTIALLY_IMPLEMENTED
                    ]
                ),
                "not_implemented": len(
                    [c for c in controls if c.status == ControlStatus.NOT_IMPLEMENTED]
                ),
            }

        return summary

    def get_controls_needing_review(self) -> List[SecurityControl]:
        """Get controls that need review."""
        return [c for c in self._controls.values() if c.needs_review]


class AccessAuditLog:
    """
    [Q3 2026] Access Control Audit Log

    Records all access events for SOC 2 compliance.
    """

    def __init__(self, max_entries: int = 100000):
        self._logs: List[AccessLog] = []
        self._max_entries = max_entries
        self._lock = threading.Lock()

    def log_access(
        self,
        user_id: str,
        action: str,
        resource: str,
        resource_type: str,
        success: bool,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AccessLog:
        """Log an access event."""
        log_id = hashlib.sha256(
            f"{user_id}{action}{resource}{time.time()}".encode()
        ).hexdigest()[:16]

        log = AccessLog(
            log_id=log_id,
            timestamp=time.time(),
            user_id=user_id,
            action=action,
            resource=resource,
            resource_type=resource_type,
            success=success,
            ip_address=ip_address,
            details=details or {},
        )

        with self._lock:
            self._logs.append(log)
            # Trim old entries if needed
            if len(self._logs) > self._max_entries:
                self._logs = self._logs[-self._max_entries :]

        return log

    def get_logs_for_user(self, user_id: str, limit: int = 100) -> List[AccessLog]:
        """Get access logs for a specific user."""
        logs = [l for l in self._logs if l.user_id == user_id]
        return logs[-limit:]

    def get_failed_access_attempts(
        self, since: Optional[float] = None
    ) -> List[AccessLog]:
        """Get failed access attempts."""
        if since is None:
            since = time.time() - (24 * 60 * 60)  # Last 24 hours
        return [l for l in self._logs if not l.success and l.timestamp >= since]

    def get_privileged_actions(self, since: Optional[float] = None) -> List[AccessLog]:
        """Get privileged action logs (admin, delete, modify permissions)."""
        privileged_actions = {"admin", "delete", "modify_permissions", "escalate"}
        if since is None:
            since = time.time() - (24 * 60 * 60)
        return [
            l
            for l in self._logs
            if l.action in privileged_actions and l.timestamp >= since
        ]

    def export_logs(self, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """Export logs for a time range."""
        return [
            l.to_dict() for l in self._logs if start_time <= l.timestamp <= end_time
        ]


class ChangeManagement:
    """
    [Q3 2026] Change Management System

    Tracks system changes for SOC 2 compliance.
    """

    def __init__(self) -> None:
        self._changes: Dict[str, ChangeRecord] = {}
        self._lock = threading.Lock()

    def create_change_request(
        self,
        title: str,
        description: str,
        change_type: str,
        requester: str,
        affected_systems: List[str],
        rollback_plan: str = "",
    ) -> ChangeRecord:
        """Create a new change request."""
        change_id = hashlib.sha256(
            f"{title}{requester}{time.time()}".encode()
        ).hexdigest()[:12]

        change = ChangeRecord(
            change_id=change_id,
            title=title,
            description=description,
            change_type=change_type,
            requester=requester,
            affected_systems=affected_systems,
            rollback_plan=rollback_plan,
        )

        with self._lock:
            self._changes[change_id] = change

        logger.info(f"Change request created: {change_id} - {title}")
        return change

    def approve_change(self, change_id: str, approver: str) -> bool:
        """Approve a change request."""
        change = self._changes.get(change_id)
        if not change or change.status != "pending":
            return False

        with self._lock:
            change.status = "approved"
            change.approver = approver
            change.approved_at = time.time()

        logger.info(f"Change {change_id} approved by {approver}")
        return True

    def implement_change(self, change_id: str, test_results: str = "") -> bool:
        """Mark a change as implemented."""
        change = self._changes.get(change_id)
        if not change or change.status != "approved":
            return False

        with self._lock:
            change.status = "implemented"
            change.implemented_at = time.time()
            change.test_results = test_results

        logger.info(f"Change {change_id} implemented")
        return True

    def rollback_change(self, change_id: str, reason: str) -> bool:
        """Rollback an implemented change."""
        change = self._changes.get(change_id)
        if not change or change.status != "implemented":
            return False

        with self._lock:
            change.status = "rolled_back"

        logger.warning(f"Change {change_id} rolled back: {reason}")
        return True

    def get_pending_changes(self) -> List[ChangeRecord]:
        """Get all pending change requests."""
        return [c for c in self._changes.values() if c.status == "pending"]

    def get_changes_by_status(self, status: str) -> List[ChangeRecord]:
        """Get changes by status."""
        return [c for c in self._changes.values() if c.status == status]


class IncidentManagement:
    """
    [Q3 2026] Security Incident Management

    Tracks and manages security incidents for SOC 2 compliance.
    """

    def __init__(self) -> None:
        self._incidents: Dict[str, SecurityIncident] = {}
        self._lock = threading.Lock()

    def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        reported_by: str,
        affected_systems: Optional[List[str]] = None,
    ) -> SecurityIncident:
        """Create a new security incident."""
        incident_id = (
            f"INC-{int(time.time())}-{hashlib.sha256(title.encode()).hexdigest()[:6]}"
        )

        incident = SecurityIncident(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            reported_by=reported_by,
            affected_systems=affected_systems or [],
            detected_at=time.time(),
        )

        with self._lock:
            self._incidents[incident_id] = incident

        logger.warning(f"Security incident created: {incident_id} ({severity.value})")
        return incident

    def assign_incident(self, incident_id: str, assignee: str) -> bool:
        """Assign an incident to a responder."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return False

        with self._lock:
            incident.assigned_to = assignee
            incident.status = IncidentStatus.INVESTIGATING

        return True

    def mitigate_incident(self, incident_id: str, remediation_steps: List[str]) -> bool:
        """Mark incident as mitigated."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return False

        with self._lock:
            incident.status = IncidentStatus.MITIGATED
            incident.mitigated_at = time.time()
            incident.remediation_steps = remediation_steps

        logger.info(f"Incident {incident_id} mitigated")
        return True

    def resolve_incident(
        self,
        incident_id: str,
        root_cause: str,
        lessons_learned: str,
    ) -> bool:
        """Resolve an incident."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return False

        with self._lock:
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = time.time()
            incident.root_cause = root_cause
            incident.lessons_learned = lessons_learned

        logger.info(f"Incident {incident_id} resolved")
        return True

    def get_open_incidents(self) -> List[SecurityIncident]:
        """Get all open incidents."""
        return [
            i
            for i in self._incidents.values()
            if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)
        ]

    def get_incidents_by_severity(
        self, severity: IncidentSeverity
    ) -> List[SecurityIncident]:
        """Get incidents by severity."""
        return [i for i in self._incidents.values() if i.severity == severity]

    def get_incident_metrics(self) -> Dict[str, Any]:
        """Get incident response metrics."""
        incidents = list(self._incidents.values())
        if not incidents:
            return {"total": 0}

        resolved = [i for i in incidents if i.status == IncidentStatus.RESOLVED]
        ttd_values = [i.time_to_detect for i in resolved if i.time_to_detect]
        ttm_values = [i.time_to_mitigate for i in resolved if i.time_to_mitigate]

        return {
            "total": len(incidents),
            "open": len(self.get_open_incidents()),
            "resolved": len(resolved),
            "by_severity": {
                sev.value: len(self.get_incidents_by_severity(sev))
                for sev in IncidentSeverity
            },
            "avg_time_to_detect_hours": (
                sum(ttd_values) / len(ttd_values) if ttd_values else None
            ),
            "avg_time_to_mitigate_hours": (
                sum(ttm_values) / len(ttm_values) if ttm_values else None
            ),
        }


class RiskRegistry:
    """
    [Q3 2026] Risk Assessment Registry

    Manages risk assessments for SOC 2 compliance.
    """

    def __init__(self) -> None:
        self._risks: Dict[str, RiskAssessment] = {}
        self._lock = threading.Lock()

    def register_risk(self, risk: RiskAssessment) -> None:
        """Register a risk."""
        with self._lock:
            self._risks[risk.risk_id] = risk
        logger.info(f"Risk registered: {risk.risk_id} - {risk.title}")

    def get_risk(self, risk_id: str) -> Optional[RiskAssessment]:
        """Get a risk by ID."""
        return self._risks.get(risk_id)

    def get_risks_by_category(
        self, category: TrustServiceCategory
    ) -> List[RiskAssessment]:
        """Get risks by category."""
        return [r for r in self._risks.values() if r.category == category]

    def get_high_risks(self) -> List[RiskAssessment]:
        """Get high and critical risks."""
        return [
            r
            for r in self._risks.values()
            if r.residual_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            and r.status == "open"
        ]

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get risk summary."""
        risks = list(self._risks.values())
        return {
            "total": len(risks),
            "open": len([r for r in risks if r.status == "open"]),
            "mitigated": len([r for r in risks if r.status == "mitigated"]),
            "by_level": {
                level.value: len([r for r in risks if r.residual_risk == level])
                for level in RiskLevel
            },
            "high_risk_count": len(self.get_high_risks()),
        }


class SOC2Compliance:
    """
    [Q3 2026] SOC 2 Compliance Manager

    Central manager for SOC 2 Type I/II compliance.
    """

    def __init__(self, organization_name: str = "WarmLogic"):
        self.organization_name = organization_name
        self.control_registry = ControlRegistry()
        self.access_audit = AccessAuditLog()
        self.change_management = ChangeManagement()
        self.incident_management = IncidentManagement()
        self.risk_registry = RiskRegistry()
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize SOC 2 compliance infrastructure."""
        try:
            self._setup_default_controls()
            self._setup_default_risks()
            self._initialized = True
            logger.info("SOC 2 Compliance infrastructure initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SOC 2 compliance: {e}")
            return False

    def _setup_default_controls(self) -> None:
        """Set up default SOC 2 controls."""
        controls = [
            # Security Controls (CC)
            SecurityControl(
                control_id="CC1.1",
                category=TrustServiceCategory.SECURITY,
                title="Security Policy",
                description="The entity has defined security policies that are communicated to personnel.",
                status=ControlStatus.IMPLEMENTED,
            ),
            SecurityControl(
                control_id="CC2.1",
                category=TrustServiceCategory.SECURITY,
                title="Access Control",
                description="Logical access to systems is restricted to authorized users.",
                status=ControlStatus.IMPLEMENTED,
            ),
            SecurityControl(
                control_id="CC3.1",
                category=TrustServiceCategory.SECURITY,
                title="Encryption",
                description="Data is encrypted in transit and at rest.",
                status=ControlStatus.IMPLEMENTED,
            ),
            SecurityControl(
                control_id="CC4.1",
                category=TrustServiceCategory.SECURITY,
                title="Change Management",
                description="Changes to systems are authorized, tested, and documented.",
                status=ControlStatus.IMPLEMENTED,
            ),
            SecurityControl(
                control_id="CC5.1",
                category=TrustServiceCategory.SECURITY,
                title="Incident Response",
                description="Security incidents are identified, reported, and resolved.",
                status=ControlStatus.IMPLEMENTED,
            ),
            # Availability Controls (A)
            SecurityControl(
                control_id="A1.1",
                category=TrustServiceCategory.AVAILABILITY,
                title="System Monitoring",
                description="System performance and availability are monitored.",
                status=ControlStatus.IMPLEMENTED,
            ),
            SecurityControl(
                control_id="A1.2",
                category=TrustServiceCategory.AVAILABILITY,
                title="Disaster Recovery",
                description="Disaster recovery plans are documented and tested.",
                status=ControlStatus.PARTIALLY_IMPLEMENTED,
            ),
            # Processing Integrity Controls (PI)
            SecurityControl(
                control_id="PI1.1",
                category=TrustServiceCategory.PROCESSING_INTEGRITY,
                title="Data Validation",
                description="Data inputs are validated for completeness and accuracy.",
                status=ControlStatus.IMPLEMENTED,
            ),
            # Confidentiality Controls (C)
            SecurityControl(
                control_id="C1.1",
                category=TrustServiceCategory.CONFIDENTIALITY,
                title="Data Classification",
                description="Data is classified according to sensitivity.",
                status=ControlStatus.IMPLEMENTED,
            ),
            # Privacy Controls (P)
            SecurityControl(
                control_id="P1.1",
                category=TrustServiceCategory.PRIVACY,
                title="Privacy Notice",
                description="Privacy practices are communicated to data subjects.",
                status=ControlStatus.IMPLEMENTED,
            ),
        ]

        for control in controls:
            self.control_registry.register_control(control)

    def _setup_default_risks(self) -> None:
        """Set up default risk assessments."""
        risks = [
            RiskAssessment(
                risk_id="RISK-001",
                title="Unauthorized Access",
                description="Risk of unauthorized access to systems or data",
                category=TrustServiceCategory.SECURITY,
                likelihood=RiskLevel.MEDIUM,
                impact=RiskLevel.HIGH,
                inherent_risk=RiskLevel.HIGH,
                residual_risk=RiskLevel.LOW,
                controls=["CC2.1", "CC3.1"],
                status="mitigated",
            ),
            RiskAssessment(
                risk_id="RISK-002",
                title="Data Breach",
                description="Risk of sensitive data exposure",
                category=TrustServiceCategory.CONFIDENTIALITY,
                likelihood=RiskLevel.LOW,
                impact=RiskLevel.CRITICAL,
                inherent_risk=RiskLevel.HIGH,
                residual_risk=RiskLevel.MEDIUM,
                controls=["CC3.1", "C1.1"],
                status="open",
            ),
            RiskAssessment(
                risk_id="RISK-003",
                title="System Downtime",
                description="Risk of unplanned system unavailability",
                category=TrustServiceCategory.AVAILABILITY,
                likelihood=RiskLevel.MEDIUM,
                impact=RiskLevel.HIGH,
                inherent_risk=RiskLevel.HIGH,
                residual_risk=RiskLevel.LOW,
                controls=["A1.1", "A1.2"],
                status="mitigated",
            ),
        ]

        for risk in risks:
            self.risk_registry.register_risk(risk)

    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive compliance report."""
        return {
            "organization": self.organization_name,
            "report_date": datetime.now(timezone.utc).isoformat(),
            "controls": {
                "summary": self.control_registry.get_compliance_summary(),
                "needing_review": len(
                    self.control_registry.get_controls_needing_review()
                ),
            },
            "incidents": self.incident_management.get_incident_metrics(),
            "risks": self.risk_registry.get_risk_summary(),
            "changes": {
                "pending": len(self.change_management.get_pending_changes()),
            },
            "audit_status": self._calculate_audit_status(),
        }

    def _calculate_audit_status(self) -> Dict[str, Any]:
        """Calculate overall audit readiness."""
        summary = self.control_registry.get_compliance_summary()
        total_controls = sum(s["total"] for s in summary.values())
        implemented = sum(s["implemented"] for s in summary.values())

        if total_controls == 0:
            score = 0
        else:
            score = (implemented / total_controls) * 100

        return {
            "readiness_score": round(score, 1),
            "status": (
                "ready" if score >= 90 else "needs_work" if score >= 70 else "not_ready"
            ),
            "open_incidents": len(self.incident_management.get_open_incidents()),
            "high_risks": len(self.risk_registry.get_high_risks()),
        }


# Global SOC 2 compliance instance
_soc2_compliance: Optional[SOC2Compliance] = None


def get_soc2_compliance() -> SOC2Compliance:
    """Get the global SOC 2 compliance instance."""
    global _soc2_compliance
    if _soc2_compliance is None:
        _soc2_compliance = SOC2Compliance()
        _soc2_compliance.initialize()
    return _soc2_compliance


def initialize_soc2(organization_name: str = "WarmLogic") -> SOC2Compliance:
    """Initialize SOC 2 compliance infrastructure."""
    global _soc2_compliance
    _soc2_compliance = SOC2Compliance(organization_name)
    _soc2_compliance.initialize()
    return _soc2_compliance
