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
[Q3 2026] GDPR Compliance Infrastructure

Implements GDPR (General Data Protection Regulation) requirements:
- Data Subject Rights (Articles 15-22)
- Consent Management (Article 7)
- Data Retention Policies (Article 5)
- Processing Records (Article 30)
- Data Breach Notification (Articles 33-34)
"""

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("GDPR")


class RequestType(Enum):
    """GDPR Data Subject Request types (Articles 15-22)."""

    ACCESS = "access"  # Article 15: Right of access
    RECTIFICATION = "rectification"  # Article 16: Right to rectification
    ERASURE = "erasure"  # Article 17: Right to erasure (right to be forgotten)
    RESTRICTION = "restriction"  # Article 18: Right to restriction of processing
    PORTABILITY = "portability"  # Article 20: Right to data portability
    OBJECTION = "objection"  # Article 21: Right to object


class RequestStatus(Enum):
    """Status of a data subject request."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ConsentPurpose(Enum):
    """Purposes for data processing consent."""

    ESSENTIAL = "essential"  # Required for service operation
    ANALYTICS = "analytics"  # Analytics and improvement
    MARKETING = "marketing"  # Marketing communications
    PROFILING = "profiling"  # Automated decision-making
    THIRD_PARTY = "third_party"  # Sharing with third parties
    RESEARCH = "research"  # Research purposes


@dataclass
class DataSubjectRequest:
    """GDPR Data Subject Request record."""

    request_id: str
    subject_id: str  # User/data subject identifier
    request_type: RequestType
    status: RequestStatus = RequestStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    deadline: Optional[float] = None  # GDPR requires response within 30 days
    description: str = ""
    result: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    handler_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.deadline is None:
            # GDPR requires response within 30 days (can extend to 60 for complex)
            self.deadline = self.created_at + (30 * 24 * 60 * 60)

    @property
    def is_overdue(self) -> bool:
        """Check if request is past deadline."""
        if self.status in (RequestStatus.COMPLETED, RequestStatus.REJECTED):
            return False
        return time.time() > self.deadline if self.deadline else False

    @property
    def days_remaining(self) -> int:
        """Days remaining until deadline."""
        if self.deadline is None:
            return 0
        remaining = self.deadline - time.time()
        return max(0, int(remaining / (24 * 60 * 60)))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "request_type": self.request_type.value,
            "status": self.status.value,
            "created_at": datetime.fromtimestamp(
                self.created_at, tz=timezone.utc
            ).isoformat(),
            "deadline": (
                datetime.fromtimestamp(self.deadline, tz=timezone.utc).isoformat()
                if self.deadline
                else None
            ),
            "is_overdue": self.is_overdue,
            "days_remaining": self.days_remaining,
            "description": self.description,
        }


@dataclass
class ConsentRecord:
    """Record of user consent."""

    consent_id: str
    subject_id: str
    purpose: ConsentPurpose
    granted: bool
    granted_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    withdrawn_at: Optional[float] = None
    source: str = "user_interface"  # How consent was collected
    version: str = "1.0"  # Consent policy version

    @property
    def is_valid(self) -> bool:
        """Check if consent is currently valid."""
        if not self.granted:
            return False
        if self.withdrawn_at is not None:
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True

    def withdraw(self) -> None:
        """Withdraw consent."""
        self.withdrawn_at = time.time()
        self.granted = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "consent_id": self.consent_id,
            "subject_id": self.subject_id,
            "purpose": self.purpose.value,
            "granted": self.granted,
            "is_valid": self.is_valid,
            "granted_at": datetime.fromtimestamp(
                self.granted_at, tz=timezone.utc
            ).isoformat(),
            "withdrawn_at": (
                datetime.fromtimestamp(self.withdrawn_at, tz=timezone.utc).isoformat()
                if self.withdrawn_at
                else None
            ),
        }


@dataclass
class DataRetentionPolicy:
    """Data retention policy configuration."""

    policy_id: str
    data_category: str
    retention_days: int
    legal_basis: str  # e.g., "consent", "contract", "legal_obligation"
    description: str = ""
    auto_delete: bool = True
    archive_before_delete: bool = True

    def is_expired(self, created_at: float) -> bool:
        """Check if data has exceeded retention period."""
        expiry = created_at + (self.retention_days * 24 * 60 * 60)
        return time.time() > expiry

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "policy_id": self.policy_id,
            "data_category": self.data_category,
            "retention_days": self.retention_days,
            "legal_basis": self.legal_basis,
            "auto_delete": self.auto_delete,
        }


@dataclass
class ProcessingRecord:
    """Record of Processing Activities (Article 30)."""

    record_id: str
    processing_activity: str
    purpose: str
    data_categories: List[str]
    data_subjects: List[str]  # Categories of data subjects
    recipients: List[str]  # Categories of recipients
    transfers_outside_eu: bool = False
    transfer_safeguards: Optional[str] = None
    retention_period: str = ""
    security_measures: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Article 30 register."""
        return {
            "record_id": self.record_id,
            "processing_activity": self.processing_activity,
            "purpose": self.purpose,
            "data_categories": self.data_categories,
            "data_subjects": self.data_subjects,
            "recipients": self.recipients,
            "transfers_outside_eu": self.transfers_outside_eu,
            "transfer_safeguards": self.transfer_safeguards,
            "retention_period": self.retention_period,
            "security_measures": self.security_measures,
        }


class DataSubjectRights:
    """
    [Q3 2026] Data Subject Rights Handler

    Implements GDPR Articles 15-22 for handling data subject requests.
    """

    def __init__(self) -> None:
        self._requests: Dict[str, DataSubjectRequest] = {}
        self._handlers: Dict[RequestType, Callable] = {}
        self._lock = threading.Lock()

    def register_handler(
        self, request_type: RequestType, handler: Callable[[DataSubjectRequest], Any]
    ) -> None:
        """Register a handler for a specific request type."""
        self._handlers[request_type] = handler

    def submit_request(
        self,
        subject_id: str,
        request_type: RequestType,
        description: str = "",
    ) -> DataSubjectRequest:
        """Submit a new data subject request."""
        request_id = hashlib.sha256(
            f"{subject_id}{request_type.value}{time.time()}".encode()
        ).hexdigest()[:16]

        request = DataSubjectRequest(
            request_id=request_id,
            subject_id=subject_id,
            request_type=request_type,
            description=description,
        )

        with self._lock:
            self._requests[request_id] = request

        logger.info(
            f"GDPR request submitted: {request_type.value} for subject {subject_id[:8]}..."
        )
        return request

    def get_request(self, request_id: str) -> Optional[DataSubjectRequest]:
        """Get a request by ID."""
        return self._requests.get(request_id)

    def get_requests_for_subject(self, subject_id: str) -> List[DataSubjectRequest]:
        """Get all requests for a data subject."""
        return [r for r in self._requests.values() if r.subject_id == subject_id]

    def process_request(self, request_id: str) -> bool:
        """Process a pending request."""
        request = self._requests.get(request_id)
        if not request:
            return False

        if request.status != RequestStatus.PENDING:
            logger.warning(f"Request {request_id} is not pending")
            return False

        handler = self._handlers.get(request.request_type)
        if not handler:
            logger.error(f"No handler for request type {request.request_type}")
            return False

        with self._lock:
            request.status = RequestStatus.IN_PROGRESS
            request.updated_at = time.time()

        try:
            result = handler(request)
            with self._lock:
                request.status = RequestStatus.COMPLETED
                request.completed_at = time.time()
                request.updated_at = time.time()
                request.result = result
            logger.info(f"GDPR request {request_id} completed")
            return True
        except Exception as e:
            with self._lock:
                request.status = RequestStatus.REJECTED
                request.rejection_reason = str(e)
                request.updated_at = time.time()
            logger.error(f"GDPR request {request_id} failed: {e}")
            return False

    def get_overdue_requests(self) -> List[DataSubjectRequest]:
        """Get all overdue requests."""
        return [r for r in self._requests.values() if r.is_overdue]

    def get_pending_requests(self) -> List[DataSubjectRequest]:
        """Get all pending requests."""
        return [r for r in self._requests.values() if r.status == RequestStatus.PENDING]


class ConsentManager:
    """
    [Q3 2026] Consent Management System

    Implements GDPR Article 7 requirements for consent management.
    """

    def __init__(self) -> None:
        self._consents: Dict[str, Dict[ConsentPurpose, ConsentRecord]] = {}
        self._lock = threading.Lock()

    def record_consent(
        self,
        subject_id: str,
        purpose: ConsentPurpose,
        granted: bool,
        source: str = "user_interface",
        expires_days: Optional[int] = None,
    ) -> ConsentRecord:
        """Record a consent decision."""
        consent_id = hashlib.sha256(
            f"{subject_id}{purpose.value}{time.time()}".encode()
        ).hexdigest()[:16]

        expires_at = None
        if expires_days:
            expires_at = time.time() + (expires_days * 24 * 60 * 60)

        record = ConsentRecord(
            consent_id=consent_id,
            subject_id=subject_id,
            purpose=purpose,
            granted=granted,
            source=source,
            expires_at=expires_at,
        )

        with self._lock:
            if subject_id not in self._consents:
                self._consents[subject_id] = {}
            self._consents[subject_id][purpose] = record

        action = "granted" if granted else "denied"
        logger.info(
            f"Consent {action} for {purpose.value} by subject {subject_id[:8]}..."
        )
        return record

    def has_consent(self, subject_id: str, purpose: ConsentPurpose) -> bool:
        """Check if valid consent exists for a purpose."""
        if subject_id not in self._consents:
            return False
        record = self._consents[subject_id].get(purpose)
        return record.is_valid if record else False

    def withdraw_consent(self, subject_id: str, purpose: ConsentPurpose) -> bool:
        """Withdraw consent for a specific purpose."""
        if subject_id not in self._consents:
            return False
        record = self._consents[subject_id].get(purpose)
        if not record:
            return False

        with self._lock:
            record.withdraw()
        logger.info(
            f"Consent withdrawn for {purpose.value} by subject {subject_id[:8]}..."
        )
        return True

    def withdraw_all_consents(self, subject_id: str) -> int:
        """Withdraw all consents for a subject."""
        if subject_id not in self._consents:
            return 0

        count = 0
        with self._lock:
            for record in self._consents[subject_id].values():
                if record.is_valid:
                    record.withdraw()
                    count += 1
        return count

    def get_consents(self, subject_id: str) -> List[ConsentRecord]:
        """Get all consent records for a subject."""
        if subject_id not in self._consents:
            return []
        return list(self._consents[subject_id].values())

    def get_consent_summary(self, subject_id: str) -> Dict[str, bool]:
        """Get consent status summary for a subject."""
        return {
            purpose.value: self.has_consent(subject_id, purpose)
            for purpose in ConsentPurpose
        }


class DataRetentionManager:
    """
    [Q3 2026] Data Retention Manager

    Implements GDPR Article 5 data minimization and storage limitation.
    """

    def __init__(self) -> None:
        self._policies: Dict[str, DataRetentionPolicy] = {}
        self._data_records: Dict[str, Dict[str, float]] = (
            {}
        )  # category -> {id: created_at}
        self._lock = threading.Lock()

    def add_policy(self, policy: DataRetentionPolicy) -> None:
        """Add a retention policy."""
        with self._lock:
            self._policies[policy.policy_id] = policy
        logger.info(
            f"Retention policy added: {policy.data_category} ({policy.retention_days} days)"
        )

    def get_policy(self, policy_id: str) -> Optional[DataRetentionPolicy]:
        """Get a retention policy by ID."""
        return self._policies.get(policy_id)

    def get_policies(self) -> List[DataRetentionPolicy]:
        """Get all retention policies."""
        return list(self._policies.values())

    def register_data(
        self, category: str, data_id: str, created_at: Optional[float] = None
    ) -> None:
        """Register data for retention tracking."""
        with self._lock:
            if category not in self._data_records:
                self._data_records[category] = {}
            self._data_records[category][data_id] = created_at or time.time()

    def get_expired_data(self, category: str) -> List[str]:
        """Get IDs of expired data in a category."""
        policy = next(
            (p for p in self._policies.values() if p.data_category == category), None
        )
        if not policy:
            return []

        expired = []
        records = self._data_records.get(category, {})
        for data_id, created_at in records.items():
            if policy.is_expired(created_at):
                expired.append(data_id)
        return expired

    def cleanup_expired(
        self, delete_callback: Callable[[str, str], bool]
    ) -> Dict[str, int]:
        """
        Clean up expired data across all categories.

        Args:
            delete_callback: Function to delete data (category, data_id) -> success

        Returns:
            Dictionary of category -> count of deleted items
        """
        results: Dict[str, int] = {}

        for policy in self._policies.values():
            if not policy.auto_delete:
                continue

            expired = self.get_expired_data(policy.data_category)
            deleted = 0

            for data_id in expired:
                try:
                    if delete_callback(policy.data_category, data_id):
                        with self._lock:
                            self._data_records[policy.data_category].pop(data_id, None)
                        deleted += 1
                except Exception as e:
                    logger.error(f"Failed to delete {data_id}: {e}")

            if deleted > 0:
                results[policy.data_category] = deleted
                logger.info(
                    f"Retention cleanup: deleted {deleted} items from {policy.data_category}"
                )

        return results


class ProcessingRegister:
    """
    [Q3 2026] Record of Processing Activities

    Implements GDPR Article 30 requirements.
    """

    def __init__(self, controller_name: str, controller_contact: str):
        self.controller_name = controller_name
        self.controller_contact = controller_contact
        self._records: Dict[str, ProcessingRecord] = {}
        self._lock = threading.Lock()

    def add_record(self, record: ProcessingRecord) -> None:
        """Add a processing activity record."""
        with self._lock:
            self._records[record.record_id] = record
        logger.info(f"Processing record added: {record.processing_activity}")

    def get_record(self, record_id: str) -> Optional[ProcessingRecord]:
        """Get a processing record by ID."""
        return self._records.get(record_id)

    def get_all_records(self) -> List[ProcessingRecord]:
        """Get all processing records."""
        return list(self._records.values())

    def export_register(self) -> Dict[str, Any]:
        """Export the complete Article 30 register."""
        return {
            "controller": {
                "name": self.controller_name,
                "contact": self.controller_contact,
            },
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "processing_activities": [r.to_dict() for r in self._records.values()],
        }


class GDPRCompliance:
    """
    [Q3 2026] GDPR Compliance Manager

    Central manager for all GDPR compliance features.
    """

    def __init__(
        self,
        controller_name: str = "WarmLogic",
        controller_contact: str = "dpo@github.com/espressolee/WarmLogic",
    ):
        self.data_subject_rights = DataSubjectRights()
        self.consent_manager = ConsentManager()
        self.retention_manager = DataRetentionManager()
        self.processing_register = ProcessingRegister(
            controller_name, controller_contact
        )
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize GDPR compliance infrastructure."""
        try:
            # Register default retention policies
            self._setup_default_policies()

            # Register default processing activities
            self._setup_default_processing_records()

            self._initialized = True
            logger.info("GDPR Compliance infrastructure initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GDPR compliance: {e}")
            return False

    def _setup_default_policies(self) -> None:
        """Set up default data retention policies."""
        policies = [
            DataRetentionPolicy(
                policy_id="audit_logs",
                data_category="audit_logs",
                retention_days=365 * 7,  # 7 years for compliance
                legal_basis="legal_obligation",
                description="Audit logs for regulatory compliance",
                auto_delete=False,
            ),
            DataRetentionPolicy(
                policy_id="user_sessions",
                data_category="session_data",
                retention_days=30,
                legal_basis="contract",
                description="User session data",
                auto_delete=True,
            ),
            DataRetentionPolicy(
                policy_id="analytics",
                data_category="analytics_data",
                retention_days=365,
                legal_basis="consent",
                description="Analytics and usage data",
                auto_delete=True,
            ),
            DataRetentionPolicy(
                policy_id="governance_decisions",
                data_category="governance_data",
                retention_days=365 * 10,  # 10 years for AI governance
                legal_basis="legitimate_interest",
                description="AI governance decisions and audit trails",
                auto_delete=False,
            ),
        ]
        for policy in policies:
            self.retention_manager.add_policy(policy)

    def _setup_default_processing_records(self) -> None:
        """Set up default processing activity records."""
        records = [
            ProcessingRecord(
                record_id="core_governance",
                processing_activity="AI Governance Processing",
                purpose="Autonomous AI governance and decision-making",
                data_categories=[
                    "governance_decisions",
                    "audit_trails",
                    "model_outputs",
                ],
                data_subjects=["ai_operators", "system_administrators"],
                recipients=["internal_systems"],
                transfers_outside_eu=False,
                retention_period="10 years",
                security_measures=[
                    "encryption_at_rest",
                    "encryption_in_transit",
                    "access_control",
                    "audit_logging",
                ],
            ),
            ProcessingRecord(
                record_id="user_auth",
                processing_activity="User Authentication",
                purpose="User identity verification and access control",
                data_categories=["identity_data", "authentication_logs"],
                data_subjects=["users", "administrators"],
                recipients=["identity_provider"],
                transfers_outside_eu=False,
                retention_period="Duration of account + 1 year",
                security_measures=[
                    "mfa",
                    "encryption",
                    "session_management",
                ],
            ),
        ]
        for record in records:
            self.processing_register.add_record(record)

    def handle_access_request(self, subject_id: str) -> Dict[str, Any]:
        """
        Handle Right of Access request (Article 15).

        Returns all personal data related to the subject.
        """
        request = self.data_subject_rights.submit_request(
            subject_id=subject_id,
            request_type=RequestType.ACCESS,
            description="Data subject access request",
        )

        # Collect all data related to the subject
        data = {
            "request_id": request.request_id,
            "subject_id": subject_id,
            "consents": [
                c.to_dict() for c in self.consent_manager.get_consents(subject_id)
            ],
            "requests": [
                r.to_dict()
                for r in self.data_subject_rights.get_requests_for_subject(subject_id)
            ],
            "processing_purposes": self.consent_manager.get_consent_summary(subject_id),
            "retention_policies": [
                p.to_dict() for p in self.retention_manager.get_policies()
            ],
        }

        return data

    def handle_erasure_request(
        self, subject_id: str, data_callback: Callable[[str], bool]
    ) -> bool:
        """
        Handle Right to Erasure request (Article 17).

        Args:
            subject_id: The data subject ID
            data_callback: Callback to delete actual data

        Returns:
            True if erasure was successful
        """
        request = self.data_subject_rights.submit_request(
            subject_id=subject_id,
            request_type=RequestType.ERASURE,
            description="Right to be forgotten request",
        )

        try:
            # Withdraw all consents
            self.consent_manager.withdraw_all_consents(subject_id)

            # Call the data deletion callback
            success = data_callback(subject_id)

            if success:
                request.status = RequestStatus.COMPLETED
                request.completed_at = time.time()
                logger.info(f"Erasure completed for subject {subject_id[:8]}...")
            else:
                request.status = RequestStatus.REJECTED
                request.rejection_reason = "Data deletion failed"

            return success
        except Exception as e:
            request.status = RequestStatus.REJECTED
            request.rejection_reason = str(e)
            logger.error(f"Erasure failed for subject {subject_id[:8]}: {e}")
            return False

    def export_data_portable(self, subject_id: str) -> Dict[str, Any]:
        """
        Handle Right to Data Portability request (Article 20).

        Returns data in a machine-readable format.
        """
        request = self.data_subject_rights.submit_request(
            subject_id=subject_id,
            request_type=RequestType.PORTABILITY,
            description="Data portability request",
        )

        # Export in JSON format (machine-readable)
        export = {
            "format_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "subject_id": subject_id,
            "consents": [
                c.to_dict() for c in self.consent_manager.get_consents(subject_id)
            ],
            "data_subject_requests": [
                r.to_dict()
                for r in self.data_subject_rights.get_requests_for_subject(subject_id)
            ],
        }

        request.status = RequestStatus.COMPLETED
        request.completed_at = time.time()
        request.result = {"export_size": len(json.dumps(export))}

        return export

    def get_compliance_status(self) -> Dict[str, Any]:
        """Get overall GDPR compliance status."""
        pending = self.data_subject_rights.get_pending_requests()
        overdue = self.data_subject_rights.get_overdue_requests()

        return {
            "initialized": self._initialized,
            "pending_requests": len(pending),
            "overdue_requests": len(overdue),
            "overdue_request_ids": [r.request_id for r in overdue],
            "retention_policies": len(self.retention_manager.get_policies()),
            "processing_records": len(self.processing_register.get_all_records()),
            "compliance_score": self._calculate_compliance_score(pending, overdue),
        }

    def _calculate_compliance_score(
        self, pending: List[DataSubjectRequest], overdue: List[DataSubjectRequest]
    ) -> float:
        """Calculate a compliance score (0-100)."""
        score = 100.0

        # Deduct for overdue requests (major violation)
        score -= len(overdue) * 20

        # Deduct for pending requests approaching deadline
        for req in pending:
            if req.days_remaining < 7:
                score -= 5
            elif req.days_remaining < 14:
                score -= 2

        return max(0, min(100, score))


# Global GDPR compliance instance
_gdpr_compliance: Optional[GDPRCompliance] = None


def get_gdpr_compliance() -> GDPRCompliance:
    """Get the global GDPR compliance instance."""
    global _gdpr_compliance
    if _gdpr_compliance is None:
        _gdpr_compliance = GDPRCompliance()
        _gdpr_compliance.initialize()
    return _gdpr_compliance


def initialize_gdpr(
    controller_name: str = "WarmLogic",
    controller_contact: str = "dpo@github.com/espressolee/WarmLogic",
) -> GDPRCompliance:
    """Initialize GDPR compliance infrastructure."""
    global _gdpr_compliance
    _gdpr_compliance = GDPRCompliance(controller_name, controller_contact)
    _gdpr_compliance.initialize()
    return _gdpr_compliance
