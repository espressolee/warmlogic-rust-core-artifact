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
Tests for GDPR Compliance module.
"""

import time
import unittest

from warm_logic.compliance.gdpr import (
    ConsentManager,
    ConsentPurpose,
    ConsentRecord,
    DataRetentionManager,
    DataRetentionPolicy,
    DataSubjectRequest,
    DataSubjectRights,
    GDPRCompliance,
    ProcessingRecord,
    ProcessingRegister,
    RequestStatus,
    RequestType,
    get_gdpr_compliance,
    initialize_gdpr,
)


class TestRequestType(unittest.TestCase):
    """Test RequestType enum."""

    def test_request_types(self):
        """Test all GDPR request types exist."""
        self.assertEqual(RequestType.ACCESS.value, "access")
        self.assertEqual(RequestType.RECTIFICATION.value, "rectification")
        self.assertEqual(RequestType.ERASURE.value, "erasure")
        self.assertEqual(RequestType.RESTRICTION.value, "restriction")
        self.assertEqual(RequestType.PORTABILITY.value, "portability")
        self.assertEqual(RequestType.OBJECTION.value, "objection")


class TestConsentPurpose(unittest.TestCase):
    """Test ConsentPurpose enum."""

    def test_consent_purposes(self):
        """Test all consent purposes exist."""
        self.assertEqual(ConsentPurpose.ESSENTIAL.value, "essential")
        self.assertEqual(ConsentPurpose.ANALYTICS.value, "analytics")
        self.assertEqual(ConsentPurpose.MARKETING.value, "marketing")
        self.assertEqual(ConsentPurpose.PROFILING.value, "profiling")


class TestDataSubjectRequest(unittest.TestCase):
    """Test DataSubjectRequest dataclass."""

    def test_request_creation(self):
        """Test request creation with defaults."""
        request = DataSubjectRequest(
            request_id="req123",
            subject_id="user456",
            request_type=RequestType.ACCESS,
        )
        self.assertEqual(request.request_id, "req123")
        self.assertEqual(request.status, RequestStatus.PENDING)
        self.assertIsNotNone(request.deadline)

    def test_deadline_calculation(self):
        """Test 30-day deadline is set."""
        request = DataSubjectRequest(
            request_id="req123",
            subject_id="user456",
            request_type=RequestType.ACCESS,
        )
        # Deadline should be approximately 30 days from now
        expected = request.created_at + (30 * 24 * 60 * 60)
        self.assertAlmostEqual(request.deadline, expected, delta=1)

    def test_is_overdue_pending(self):
        """Test overdue check for pending request."""
        request = DataSubjectRequest(
            request_id="req123",
            subject_id="user456",
            request_type=RequestType.ACCESS,
            deadline=time.time() - 1,  # Past deadline
        )
        self.assertTrue(request.is_overdue)

    def test_is_overdue_completed(self):
        """Test completed requests are never overdue."""
        request = DataSubjectRequest(
            request_id="req123",
            subject_id="user456",
            request_type=RequestType.ACCESS,
            status=RequestStatus.COMPLETED,
            deadline=time.time() - 1,  # Past deadline
        )
        self.assertFalse(request.is_overdue)

    def test_days_remaining(self):
        """Test days remaining calculation."""
        request = DataSubjectRequest(
            request_id="req123",
            subject_id="user456",
            request_type=RequestType.ACCESS,
            deadline=time.time() + (10 * 24 * 60 * 60),  # 10 days
        )
        self.assertGreaterEqual(request.days_remaining, 9)
        self.assertLessEqual(request.days_remaining, 10)

    def test_to_dict(self):
        """Test dictionary conversion."""
        request = DataSubjectRequest(
            request_id="req123",
            subject_id="user456",
            request_type=RequestType.ACCESS,
        )
        result = request.to_dict()

        self.assertEqual(result["request_id"], "req123")
        self.assertEqual(result["request_type"], "access")
        self.assertIn("deadline", result)


class TestConsentRecord(unittest.TestCase):
    """Test ConsentRecord dataclass."""

    def test_consent_creation(self):
        """Test consent record creation."""
        consent = ConsentRecord(
            consent_id="con123",
            subject_id="user456",
            purpose=ConsentPurpose.ANALYTICS,
            granted=True,
        )
        self.assertTrue(consent.is_valid)

    def test_consent_not_granted(self):
        """Test consent not granted is invalid."""
        consent = ConsentRecord(
            consent_id="con123",
            subject_id="user456",
            purpose=ConsentPurpose.MARKETING,
            granted=False,
        )
        self.assertFalse(consent.is_valid)

    def test_consent_expired(self):
        """Test expired consent is invalid."""
        consent = ConsentRecord(
            consent_id="con123",
            subject_id="user456",
            purpose=ConsentPurpose.ANALYTICS,
            granted=True,
            expires_at=time.time() - 1,  # Expired
        )
        self.assertFalse(consent.is_valid)

    def test_consent_withdraw(self):
        """Test withdrawing consent."""
        consent = ConsentRecord(
            consent_id="con123",
            subject_id="user456",
            purpose=ConsentPurpose.ANALYTICS,
            granted=True,
        )
        self.assertTrue(consent.is_valid)

        consent.withdraw()
        self.assertFalse(consent.is_valid)
        self.assertIsNotNone(consent.withdrawn_at)


class TestDataRetentionPolicy(unittest.TestCase):
    """Test DataRetentionPolicy dataclass."""

    def test_policy_creation(self):
        """Test policy creation."""
        policy = DataRetentionPolicy(
            policy_id="pol123",
            data_category="user_data",
            retention_days=365,
            legal_basis="consent",
        )
        self.assertEqual(policy.retention_days, 365)

    def test_is_expired(self):
        """Test expiration check."""
        policy = DataRetentionPolicy(
            policy_id="pol123",
            data_category="user_data",
            retention_days=30,
            legal_basis="consent",
        )

        # Data created 31 days ago should be expired
        old_timestamp = time.time() - (31 * 24 * 60 * 60)
        self.assertTrue(policy.is_expired(old_timestamp))

        # Data created 29 days ago should not be expired
        recent_timestamp = time.time() - (29 * 24 * 60 * 60)
        self.assertFalse(policy.is_expired(recent_timestamp))


class TestProcessingRecord(unittest.TestCase):
    """Test ProcessingRecord dataclass."""

    def test_record_creation(self):
        """Test processing record creation."""
        record = ProcessingRecord(
            record_id="rec123",
            processing_activity="User Analytics",
            purpose="Service improvement",
            data_categories=["usage_data"],
            data_subjects=["users"],
            recipients=["internal"],
        )
        self.assertEqual(record.processing_activity, "User Analytics")
        self.assertFalse(record.transfers_outside_eu)

    def test_to_dict(self):
        """Test Article 30 format conversion."""
        record = ProcessingRecord(
            record_id="rec123",
            processing_activity="User Analytics",
            purpose="Service improvement",
            data_categories=["usage_data"],
            data_subjects=["users"],
            recipients=["internal"],
        )
        result = record.to_dict()

        self.assertIn("processing_activity", result)
        self.assertIn("security_measures", result)


class TestDataSubjectRights(unittest.TestCase):
    """Test DataSubjectRights class."""

    def test_submit_request(self):
        """Test submitting a request."""
        rights = DataSubjectRights()
        request = rights.submit_request(
            subject_id="user123",
            request_type=RequestType.ACCESS,
            description="I want my data",
        )

        self.assertIsNotNone(request.request_id)
        self.assertEqual(request.status, RequestStatus.PENDING)

    def test_get_request(self):
        """Test retrieving a request."""
        rights = DataSubjectRights()
        submitted = rights.submit_request(
            subject_id="user123",
            request_type=RequestType.ACCESS,
        )

        retrieved = rights.get_request(submitted.request_id)
        self.assertEqual(submitted.request_id, retrieved.request_id)

    def test_get_requests_for_subject(self):
        """Test getting all requests for a subject."""
        rights = DataSubjectRights()
        rights.submit_request("user123", RequestType.ACCESS)
        rights.submit_request("user123", RequestType.ERASURE)
        rights.submit_request("user456", RequestType.ACCESS)

        user123_requests = rights.get_requests_for_subject("user123")
        self.assertEqual(len(user123_requests), 2)

    def test_register_and_process_handler(self):
        """Test registering and processing with a handler."""
        rights = DataSubjectRights()

        # Register handler
        handler_called = []

        def access_handler(request):
            handler_called.append(request.request_id)
            return {"data": "user data"}

        rights.register_handler(RequestType.ACCESS, access_handler)

        # Submit and process
        request = rights.submit_request("user123", RequestType.ACCESS)
        result = rights.process_request(request.request_id)

        self.assertTrue(result)
        self.assertEqual(len(handler_called), 1)
        self.assertEqual(request.status, RequestStatus.COMPLETED)

    def test_get_pending_requests(self):
        """Test getting pending requests."""
        rights = DataSubjectRights()
        rights.submit_request("user123", RequestType.ACCESS)
        rights.submit_request("user456", RequestType.ERASURE)

        pending = rights.get_pending_requests()
        self.assertEqual(len(pending), 2)


class TestConsentManager(unittest.TestCase):
    """Test ConsentManager class."""

    def test_record_consent(self):
        """Test recording consent."""
        manager = ConsentManager()
        record = manager.record_consent(
            subject_id="user123",
            purpose=ConsentPurpose.ANALYTICS,
            granted=True,
        )

        self.assertTrue(record.is_valid)
        self.assertTrue(manager.has_consent("user123", ConsentPurpose.ANALYTICS))

    def test_no_consent(self):
        """Test checking consent that doesn't exist."""
        manager = ConsentManager()
        self.assertFalse(manager.has_consent("user123", ConsentPurpose.MARKETING))

    def test_withdraw_consent(self):
        """Test withdrawing consent."""
        manager = ConsentManager()
        manager.record_consent("user123", ConsentPurpose.ANALYTICS, True)

        result = manager.withdraw_consent("user123", ConsentPurpose.ANALYTICS)
        self.assertTrue(result)
        self.assertFalse(manager.has_consent("user123", ConsentPurpose.ANALYTICS))

    def test_withdraw_all_consents(self):
        """Test withdrawing all consents."""
        manager = ConsentManager()
        manager.record_consent("user123", ConsentPurpose.ANALYTICS, True)
        manager.record_consent("user123", ConsentPurpose.MARKETING, True)
        manager.record_consent("user123", ConsentPurpose.PROFILING, True)

        count = manager.withdraw_all_consents("user123")
        self.assertEqual(count, 3)

    def test_get_consent_summary(self):
        """Test getting consent summary."""
        manager = ConsentManager()
        manager.record_consent("user123", ConsentPurpose.ANALYTICS, True)
        manager.record_consent("user123", ConsentPurpose.MARKETING, False)

        summary = manager.get_consent_summary("user123")
        self.assertTrue(summary["analytics"])
        self.assertFalse(summary["marketing"])


class TestDataRetentionManager(unittest.TestCase):
    """Test DataRetentionManager class."""

    def test_add_policy(self):
        """Test adding a retention policy."""
        manager = DataRetentionManager()
        policy = DataRetentionPolicy(
            policy_id="pol123",
            data_category="user_data",
            retention_days=365,
            legal_basis="consent",
        )
        manager.add_policy(policy)

        retrieved = manager.get_policy("pol123")
        self.assertEqual(retrieved.data_category, "user_data")

    def test_register_data(self):
        """Test registering data for tracking."""
        manager = DataRetentionManager()
        policy = DataRetentionPolicy(
            policy_id="pol123",
            data_category="user_data",
            retention_days=30,
            legal_basis="consent",
        )
        manager.add_policy(policy)

        manager.register_data("user_data", "data001")
        manager.register_data("user_data", "data002")

        # New data should not be expired
        expired = manager.get_expired_data("user_data")
        self.assertEqual(len(expired), 0)

    def test_get_expired_data(self):
        """Test getting expired data."""
        manager = DataRetentionManager()
        policy = DataRetentionPolicy(
            policy_id="pol123",
            data_category="user_data",
            retention_days=30,
            legal_basis="consent",
        )
        manager.add_policy(policy)

        # Register old data
        old_timestamp = time.time() - (31 * 24 * 60 * 60)
        manager.register_data("user_data", "old_data", old_timestamp)
        manager.register_data("user_data", "new_data")  # Current time

        expired = manager.get_expired_data("user_data")
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0], "old_data")


class TestProcessingRegister(unittest.TestCase):
    """Test ProcessingRegister class."""

    def test_add_record(self):
        """Test adding a processing record."""
        register = ProcessingRegister("WarmLogic", "dpo@github.com/espressolee/WarmLogic")
        record = ProcessingRecord(
            record_id="rec123",
            processing_activity="Analytics",
            purpose="Service improvement",
            data_categories=["usage"],
            data_subjects=["users"],
            recipients=["internal"],
        )
        register.add_record(record)

        retrieved = register.get_record("rec123")
        self.assertEqual(retrieved.processing_activity, "Analytics")

    def test_export_register(self):
        """Test exporting Article 30 register."""
        register = ProcessingRegister("WarmLogic", "dpo@github.com/espressolee/WarmLogic")
        record = ProcessingRecord(
            record_id="rec123",
            processing_activity="Analytics",
            purpose="Service improvement",
            data_categories=["usage"],
            data_subjects=["users"],
            recipients=["internal"],
        )
        register.add_record(record)

        export = register.export_register()
        self.assertEqual(export["controller"]["name"], "WarmLogic")
        self.assertEqual(len(export["processing_activities"]), 1)


class TestGDPRCompliance(unittest.TestCase):
    """Test GDPRCompliance class."""

    def test_initialization(self):
        """Test GDPR compliance initialization."""
        compliance = GDPRCompliance()
        result = compliance.initialize()

        self.assertTrue(result)
        self.assertTrue(compliance._initialized)

    def test_default_policies_created(self):
        """Test default retention policies are created."""
        compliance = GDPRCompliance()
        compliance.initialize()

        policies = compliance.retention_manager.get_policies()
        self.assertGreater(len(policies), 0)

    def test_default_processing_records_created(self):
        """Test default processing records are created."""
        compliance = GDPRCompliance()
        compliance.initialize()

        records = compliance.processing_register.get_all_records()
        self.assertGreater(len(records), 0)

    def test_handle_access_request(self):
        """Test handling access request."""
        compliance = GDPRCompliance()
        compliance.initialize()

        data = compliance.handle_access_request("user123")

        self.assertIn("subject_id", data)
        self.assertIn("consents", data)
        self.assertIn("retention_policies", data)

    def test_handle_erasure_request(self):
        """Test handling erasure request."""
        compliance = GDPRCompliance()
        compliance.initialize()

        # Record some consents first
        compliance.consent_manager.record_consent(
            "user123", ConsentPurpose.ANALYTICS, True
        )

        # Mock delete callback
        delete_called = []

        def delete_callback(subject_id):
            delete_called.append(subject_id)
            return True

        result = compliance.handle_erasure_request("user123", delete_callback)

        self.assertTrue(result)
        self.assertEqual(len(delete_called), 1)
        self.assertFalse(
            compliance.consent_manager.has_consent("user123", ConsentPurpose.ANALYTICS)
        )

    def test_export_data_portable(self):
        """Test data portability export."""
        compliance = GDPRCompliance()
        compliance.initialize()

        compliance.consent_manager.record_consent(
            "user123", ConsentPurpose.ESSENTIAL, True
        )

        export = compliance.export_data_portable("user123")

        self.assertEqual(export["format_version"], "1.0")
        self.assertEqual(export["subject_id"], "user123")
        self.assertIn("consents", export)

    def test_get_compliance_status(self):
        """Test getting compliance status."""
        compliance = GDPRCompliance()
        compliance.initialize()

        status = compliance.get_compliance_status()

        self.assertTrue(status["initialized"])
        self.assertIn("pending_requests", status)
        self.assertIn("compliance_score", status)

    def test_compliance_score_calculation(self):
        """Test compliance score with overdue requests."""
        compliance = GDPRCompliance()
        compliance.initialize()

        # Create overdue request
        request = DataSubjectRequest(
            request_id="overdue",
            subject_id="user123",
            request_type=RequestType.ACCESS,
            deadline=time.time() - 1,
        )
        compliance.data_subject_rights._requests["overdue"] = request

        status = compliance.get_compliance_status()
        self.assertLess(status["compliance_score"], 100)


class TestGlobalFunctions(unittest.TestCase):
    """Test global GDPR functions."""

    def test_get_gdpr_compliance(self):
        """Test getting global GDPR compliance instance."""
        compliance = get_gdpr_compliance()
        self.assertIsNotNone(compliance)
        self.assertIsInstance(compliance, GDPRCompliance)

    def test_initialize_gdpr(self):
        """Test initializing GDPR with custom controller."""
        compliance = initialize_gdpr(
            controller_name="TestCorp",
            controller_contact="dpo@testcorp.io",
        )
        self.assertEqual(compliance.processing_register.controller_name, "TestCorp")


if __name__ == "__main__":
    unittest.main()
