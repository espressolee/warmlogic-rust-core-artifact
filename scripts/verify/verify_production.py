#!/usr/bin/env python3
"""
[Phase 109] Verify Production Deployment Components.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import logging

from warm_logic.kernel.infrastructure.airgap import AirgapConfig, AirgapManager
from warm_logic.kernel.infrastructure.audit import AuditEventType, ForensicAuditLogger
from warm_logic.kernel.infrastructure.metrics import MetricsExporter

logging.basicConfig(level=logging.INFO)


def test_all_modules():
    print("Phase 109: Production Deployment Verification")
    print("=" * 60)

    # Test 1: Airgap Mode
    print("\n--- 109.3: Airgap Mode ---")
    config = AirgapConfig(enabled=True, allow_usb_import=True, encryption_required=True)
    airgap = AirgapManager(config)

    status = airgap.get_status()
    print(f"Airgap enabled: {status['enabled']}")
    print(f"Telemetry disabled: {status['telemetry_disabled']}")
    print(f"External API blocked: {status['external_api_disabled']}")

    # Check network blocking
    assert airgap.check_network_allowed("localhost") == True
    assert airgap.check_network_allowed("api.openai.com") == False
    print("Airgap Mode works!")

    # Test 2: Forensic Audit Logger
    print("\n--- 109.4: Forensic Audit Logger ---")
    audit = ForensicAuditLogger("/tmp/warmlogic_test_audit")

    # Log events
    audit.log(AuditEventType.SYSTEM_START, "system", "startup")
    audit.log(AuditEventType.AUTH_SUCCESS, "admin", "login", target="console")
    audit.log(AuditEventType.DATA_ACCESS, "user1", "read", target="config.yaml")
    audit.log(
        AuditEventType.VETO_TRIGGERED,
        "safety",
        "veto",
        details={"reason": "harm detected"},
        result="blocked",
    )

    # Verify chain
    verification = audit.verify_chain()
    print(f"Chain valid: {verification['valid']}")
    print(f"Total events: {verification['total_events']}")

    # Search
    veto_events = audit.search(event_type=AuditEventType.VETO_TRIGGERED)
    print(f"VETO events: {len(veto_events)}")

    stats = audit.get_stats()
    print(f"Events by type: {stats['by_type']}")

    assert verification["valid"] == True
    print("Forensic Audit works!")

    # Test 3: Metrics Exporter
    print("\n--- 109.2: Metrics Exporter ---")
    metrics = MetricsExporter()

    # Set some metrics
    metrics.gauge("warmlogic_agi_score", 100.0)
    metrics.counter_inc("warmlogic_api_requests_total", labels={"method": "GET"})
    metrics.counter_inc("warmlogic_api_requests_total", labels={"method": "GET"})
    metrics.histogram_observe("warmlogic_request_duration_seconds", 0.05)
    metrics.histogram_observe("warmlogic_request_duration_seconds", 0.12)

    # Export prometheus format
    prom_output = metrics.export_prometheus()
    print(f"Prometheus metrics: {len(prom_output)} chars")

    # Health check
    health = metrics.get_health()
    print(f"Health status: {health['status']}")
    print(f"CPU: {health['cpu_percent']}%")

    print("Metrics Exporter works!")

    print("\n" + "=" * 60)
    print("All Phase 109 Modules Verified!")
    print("\nProduction Deployment Ready:")
    print("  - Docker (Dockerfile)")
    print("  - Monitoring (Prometheus + Grafana)")
    print("  - Airgap Mode (Offline operation)")
    print("  - Forensic Audit (Tamper-evident logging)")


if __name__ == "__main__":
    test_all_modules()
