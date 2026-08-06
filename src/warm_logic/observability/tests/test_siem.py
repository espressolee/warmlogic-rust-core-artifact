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
Tests for SIEM Integration module.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.observability.siem import (
    AuditEvent,
    DatadogExporter,
    EventSeverity,
    SIEMConfig,
    SIEMManager,
    SIEMProvider,
    SplunkHECExporter,
    export_audit_event,
    export_consensus_event,
    export_governance_event,
    export_security_event,
    get_siem_manager,
)


class TestSIEMConfig(unittest.TestCase):
    """Test SIEMConfig dataclass."""

    def test_default_config(self):
        """Test default SIEM configuration."""
        config = SIEMConfig(provider=SIEMProvider.SPLUNK)
        self.assertEqual(config.provider, SIEMProvider.SPLUNK)
        self.assertFalse(config.enabled)
        self.assertEqual(config.batch_size, 100)
        self.assertEqual(config.flush_interval_seconds, 5.0)

    def test_splunk_config(self):
        """Test Splunk HEC configuration."""
        config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            enabled=True,
            splunk_hec_url="https://splunk.example.com:8088/services/collector",
            splunk_hec_token="test-token-12345",
            splunk_index="warmlogic-prod",
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.splunk_index, "warmlogic-prod")

    def test_datadog_config(self):
        """Test Datadog configuration."""
        # Test credentials - not real values
        test_dd_key = "test-api-key"
        config = SIEMConfig(
            provider=SIEMProvider.DATADOG,
            enabled=True,
            datadog_api_key=test_dd_key,
            datadog_site="datadoghq.eu",
            datadog_env="staging",
        )
        self.assertEqual(config.provider, SIEMProvider.DATADOG)
        self.assertEqual(config.datadog_site, "datadoghq.eu")


class TestEventSeverity(unittest.TestCase):
    """Test EventSeverity enum."""

    def test_severity_values(self):
        """Test severity values map to CEF standards."""
        self.assertEqual(EventSeverity.UNKNOWN.value, 0)
        self.assertEqual(EventSeverity.LOW.value, 3)
        self.assertEqual(EventSeverity.MEDIUM.value, 5)
        self.assertEqual(EventSeverity.HIGH.value, 7)
        self.assertEqual(EventSeverity.CRITICAL.value, 10)


class TestAuditEvent(unittest.TestCase):
    """Test AuditEvent dataclass."""

    def test_event_creation(self):
        """Test basic audit event creation."""
        event = AuditEvent(
            event_id="evt123",
            timestamp=time.time(),
            event_type="auth.login",
            severity=EventSeverity.MEDIUM,
            source="warmlogic:auth",
            message="User login successful",
            actor_id="user123",
        )
        self.assertEqual(event.event_id, "evt123")
        self.assertEqual(event.event_type, "auth.login")
        self.assertEqual(event.outcome, "success")

    def test_to_json(self):
        """Test JSON serialization."""
        event = AuditEvent(
            event_id="evt456",
            timestamp=1707840000.0,  # Fixed timestamp for testing
            event_type="governance.decision",
            severity=EventSeverity.HIGH,
            source="warmlogic:governance",
            message="Patch approved",
            actor_id="council",
            resource_id="patch-001",
            details={"votes": 3},
        )
        result = event.to_json()

        self.assertEqual(result["event_id"], "evt456")
        self.assertEqual(result["event_type"], "governance.decision")
        self.assertEqual(result["severity"], "HIGH")
        self.assertEqual(result["actor"]["id"], "council")
        self.assertEqual(result["details"]["votes"], 3)

    def test_to_cef(self):
        """Test CEF format conversion."""
        config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            cef_vendor="WarmLogic",
            cef_product="WarmLogic",
            cef_version="1.1.0",
        )
        event = AuditEvent(
            event_id="evt789",
            timestamp=1707840000.0,
            event_type="security.threat",
            severity=EventSeverity.CRITICAL,
            source="warmlogic:security",
            message="Intrusion attempt detected",
            source_ip="192.168.1.100",
        )
        cef = event.to_cef(config)

        self.assertIn("CEF:0|Resonance|WarmLogic|1.1.0|", cef)
        self.assertIn("security.threat", cef)
        self.assertIn("|10|", cef)  # Critical severity

    def test_network_context(self):
        """Test network context in JSON."""
        event = AuditEvent(
            event_id="net001",
            timestamp=time.time(),
            event_type="network.connection",
            severity=EventSeverity.LOW,
            source="warmlogic:mesh",
            message="Peer connected",
            source_ip="10.0.0.1",
            destination_ip="10.0.0.2",
        )
        result = event.to_json()

        self.assertIsNotNone(result["network"])
        self.assertEqual(result["network"]["source_ip"], "10.0.0.1")
        self.assertEqual(result["network"]["destination_ip"], "10.0.0.2")


class TestSplunkHECExporter(unittest.TestCase):
    """Test SplunkHECExporter class."""

    def test_exporter_init_disabled(self):
        """Test exporter with disabled config."""
        config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            enabled=False,
        )
        exporter = SplunkHECExporter(config)
        result = exporter.initialize()
        self.assertTrue(result)  # Should succeed but be disabled

    def test_exporter_init_enabled(self):
        """Test exporter with enabled config."""
        config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            enabled=True,
            splunk_hec_url="https://splunk.test:8088/services/collector",
            splunk_hec_token="test-token",
        )
        exporter = SplunkHECExporter(config)
        result = exporter.initialize()
        self.assertTrue(result)
        exporter.shutdown(timeout=1.0)

    def test_stats(self):
        """Test exporter statistics."""
        config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            enabled=False,
        )
        exporter = SplunkHECExporter(config)
        stats = exporter.stats

        self.assertIn("sent", stats)
        self.assertIn("failed", stats)
        self.assertIn("queued", stats)
        self.assertEqual(stats["sent"], 0)


class TestDatadogExporter(unittest.TestCase):
    """Test DatadogExporter class."""

    def test_exporter_init(self):
        """Test Datadog exporter initialization."""
        test_key = "test-key"
        config = SIEMConfig(
            provider=SIEMProvider.DATADOG,
            enabled=True,
            datadog_api_key=test_key,
        )
        exporter = DatadogExporter(config)
        result = exporter.initialize()
        self.assertTrue(result)
        exporter.shutdown(timeout=1.0)

    def test_severity_mapping(self):
        """Test severity to Datadog status mapping."""
        self.assertEqual(
            DatadogExporter._severity_to_dd_status(EventSeverity.CRITICAL), "critical"
        )
        self.assertEqual(
            DatadogExporter._severity_to_dd_status(EventSeverity.HIGH), "error"
        )
        self.assertEqual(
            DatadogExporter._severity_to_dd_status(EventSeverity.MEDIUM), "warn"
        )
        self.assertEqual(
            DatadogExporter._severity_to_dd_status(EventSeverity.LOW), "info"
        )


class TestSIEMManager(unittest.TestCase):
    """Test SIEMManager class."""

    def test_manager_no_exporters(self):
        """Test manager with no exporters."""
        manager = SIEMManager()
        self.assertFalse(manager.is_enabled)
        result = manager.initialize()
        self.assertTrue(result)

    def test_manager_with_splunk(self):
        """Test manager with Splunk exporter."""
        config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            enabled=True,
            splunk_hec_url="https://splunk.test:8088/services/collector",
            splunk_hec_token="test-token",
        )
        manager = SIEMManager([config])
        self.assertTrue(manager.is_enabled)
        manager.initialize()
        manager.shutdown(timeout=1.0)

    def test_manager_multi_provider(self):
        """Test manager with multiple providers."""
        test_dd_key = "test-key"
        splunk_config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            enabled=True,
            splunk_hec_url="https://splunk.test:8088/services/collector",
            splunk_hec_token="test-token",
        )
        datadog_config = SIEMConfig(
            provider=SIEMProvider.DATADOG,
            enabled=True,
            datadog_api_key=test_dd_key,
        )
        manager = SIEMManager([splunk_config, datadog_config])
        self.assertTrue(manager.is_enabled)
        manager.initialize()

        stats = manager.stats
        self.assertIn("splunk", stats)
        self.assertIn("datadog", stats)

        manager.shutdown(timeout=1.0)

    def test_export_event(self):
        """Test event export through manager."""
        config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            enabled=True,
            splunk_hec_url="https://splunk.test:8088/services/collector",
            splunk_hec_token="test-token",
        )
        manager = SIEMManager([config])
        manager.initialize()

        event = AuditEvent(
            event_id="test001",
            timestamp=time.time(),
            event_type="test.event",
            severity=EventSeverity.LOW,
            source="test",
            message="Test event",
        )
        manager.export(event)

        # Give worker time to queue
        time.sleep(0.1)
        stats = manager.stats
        self.assertGreaterEqual(stats["splunk"]["queued"], 0)

        manager.shutdown(timeout=1.0)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience export functions."""

    def test_get_siem_manager(self):
        """Test getting global SIEM manager."""
        manager = get_siem_manager()
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager, SIEMManager)

    @patch("warm_logic.observability.siem.get_siem_manager")
    def test_export_audit_event(self, mock_get_manager):
        """Test export_audit_event function."""
        mock_manager = MagicMock()
        mock_manager.is_enabled = True
        mock_get_manager.return_value = mock_manager

        export_audit_event(
            event_type="auth.login",
            message="User logged in",
            severity=EventSeverity.LOW,
            actor_id="user123",
        )

        mock_manager.export.assert_called_once()
        call_args = mock_manager.export.call_args[0][0]
        self.assertEqual(call_args.event_type, "auth.login")

    @patch("warm_logic.observability.siem.get_siem_manager")
    def test_export_governance_event(self, mock_get_manager):
        """Test export_governance_event function."""
        mock_manager = MagicMock()
        mock_manager.is_enabled = True
        mock_get_manager.return_value = mock_manager

        export_governance_event(
            action="patch",
            decision="approved",
            actor_id="council",
            resource_id="patch-001",
        )

        mock_manager.export.assert_called_once()

    @patch("warm_logic.observability.siem.get_siem_manager")
    def test_export_security_event(self, mock_get_manager):
        """Test export_security_event function."""
        mock_manager = MagicMock()
        mock_manager.is_enabled = True
        mock_get_manager.return_value = mock_manager

        export_security_event(
            threat_type="intrusion",
            description="Unauthorized access attempt",
            severity=EventSeverity.CRITICAL,
            source_ip="10.0.0.99",
        )

        mock_manager.export.assert_called_once()
        call_args = mock_manager.export.call_args[0][0]
        self.assertEqual(call_args.severity, EventSeverity.CRITICAL)

    @patch("warm_logic.observability.siem.get_siem_manager")
    def test_export_consensus_event(self, mock_get_manager):
        """Test export_consensus_event function."""
        mock_manager = MagicMock()
        mock_manager.is_enabled = True
        mock_get_manager.return_value = mock_manager

        export_consensus_event(
            round_id="round-42",
            outcome="committed",
            participants=5,
            quorum_reached=True,
        )

        mock_manager.export.assert_called_once()


class TestEnvironmentInitialization(unittest.TestCase):
    """Test environment-based initialization."""

    @patch.dict(
        "os.environ",
        {
            "SIEM_SPLUNK_ENABLED": "true",
            "SIEM_SPLUNK_HEC_URL": "https://splunk.test:8088/services/collector",
            "SIEM_SPLUNK_HEC_TOKEN": "env-token",
            "SIEM_SPLUNK_INDEX": "warmlogic-env",
        },
    )
    def test_splunk_from_env(self):
        """Test Splunk configuration from environment."""
        from warm_logic.observability.siem import initialize_siem_from_env

        manager = initialize_siem_from_env()
        self.assertTrue(manager.is_enabled)
        self.assertIn(SIEMProvider.SPLUNK, manager._exporters)
        manager.shutdown(timeout=1.0)

    @patch.dict(
        "os.environ",
        {
            "SIEM_DATADOG_ENABLED": "true",
            "SIEM_DATADOG_API_KEY": "env-dd-key",
            "SIEM_DATADOG_SITE": "datadoghq.eu",
        },
    )
    def test_datadog_from_env(self):
        """Test Datadog configuration from environment."""
        from warm_logic.observability.siem import initialize_siem_from_env

        manager = initialize_siem_from_env()
        self.assertTrue(manager.is_enabled)
        self.assertIn(SIEMProvider.DATADOG, manager._exporters)
        manager.shutdown(timeout=1.0)


if __name__ == "__main__":
    unittest.main()
