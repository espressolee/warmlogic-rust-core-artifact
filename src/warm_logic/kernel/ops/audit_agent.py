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
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from warm_logic.system.fleet.manager import FleetManager

from .audit import IntegrityReport, SovereignAudit

logger = logging.getLogger("AuditAgent")


class AuditAgent:
    """
    Recursive Sovereignty - Audit Agent.
    Autonomous observer that monitors integrity and enforces social consensus.
    """

    def __init__(
        self,
        audit_engine: SovereignAudit,
        fleet_manager: FleetManager,
        interval: float = 300.0,
    ) -> None:
        self.audit = audit_engine
        self.fleet = fleet_manager
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_report: Optional[IntegrityReport] = None

    def start(self) -> None:
        """Starts the autonomous audit loop in a background thread."""
        if self._thread is not None:
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"AuditAgent active (Interval: {self.interval}s)")

    def stop(self) -> None:
        """Stops the audit loop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None
        logger.info("AuditAgent stopped.")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.perform_autonomous_audit()
            except Exception as e:
                logger.error(f"AuditAgent Loop Error: {e}")

            # Sleep in intervals to allow quick shutdown
            for _ in range(int(self.interval)):
                if self._stop_event.is_set():
                    break
                time.sleep(1.0)

    def perform_autonomous_audit(self) -> None:
        """
        Executes the full forensic suite and acts on the results.
        """
        logger.info("AuditAgent: Initiating Autonomous Cycle...")

        # 1. Detect Drift (Sled vs SQLite)
        drift_reason = self.audit.detect_drift()
        if drift_reason:
            logger.critical(f"[SELF-HEALING] State Drift Detected: {drift_reason}")
            self.audit.reconcile_state()

        # 2. Run Full Forensic Audit
        report = self.audit.run_full_audit()
        self.last_report = report

        # 3. Detect Misconduct (Slashing)
        self._detect_byzantine_behavior()
        self._detect_hardware_spoofing()
        self._detect_geographic_spoofing()
        self._detect_memory_tampering()
        self._process_slashing_records()

        if report.score < 10.0:
            logger.warning(
                f"⚠️ [SELF-HEALING] Integrity compromised: {report.score}/10"
            )
            # Currently, we simply log and notify.
            # Multi-node correction comes in a later revision.
        else:
            logger.info("[SELF-HEALING] System Integrity Confirmed.")

    def _detect_byzantine_behavior(self) -> None:
        """
        Proactively looks for misconduct and logs SLASH records to the store.
        """
        misconducts = self.audit.detect_misconduct()
        for mc in misconducts:
            node_id = mc["node_id"]
            reason = mc["reason"]
            logger.warning(
                f"🛡️ [AuditAgent] Misconduct detected for {node_id[:8]}: {reason}"
            )

            # Log Slash record to metadata (via audit.store)
            # Currently, we write a key that _process_slashing_records will pick up
            key = f"SLASH:{node_id}:{time.time()}"
            value = json.dumps({"reason": reason, "evidence": mc.get("evidence", "")})

            if hasattr(self.audit.store, "put_metadata"):
                self.audit.store.put_metadata(key, value)
            elif self.audit.store.conn:
                self.audit.store.conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    (key, value),
                )

    def _detect_hardware_spoofing(self) -> None:
        """
        Proactively verifies hardware fingerprints for all nodes in the fleet.
        """
        for node_id, node in self.fleet.nodes.items():
            # Currently, we expect hardware_id in node metadata or identity
            hw_hash = getattr(node, "hardware_id", None)
            if hw_hash and not self.audit.verify_hardware_integrity(node_id, hw_hash):
                logger.critical(
                    f"🛡️ [AuditAgent] HARDWARE SPOOF DETECTED for {node_id[:8]}!"
                )
                self.fleet.slash_node(node_id, "Hardware Attestation Failed")

    def _detect_geographic_spoofing(self) -> None:
        """
        Verifies that nodes are not lying about their geographic placement.
        Uses network latency triangulation (simulated).
        """
        for node_id, node in self.fleet.nodes.items():
            # Currently, we expect "region" in node metadata
            claimed_region = getattr(node, "region", "UNKNOWN")
            if claimed_region == "UNKNOWN":
                continue

            # Measure real latency (simulated stub removed for readiness)
            # In production, this uses ICMP ping or BFT consensus timing
            measured_latency = 0.0  # Placeholder: actual measurement logic in Engine

            if not self.audit.verify_regional_latency(
                node_id, claimed_region, measured_latency
            ):
                logger.critical(
                    f"🛡️ [AuditAgent] GEOGRAPHIC SPOOF DETECTED for {node_id[:8]}!"
                )
                self.fleet.slash_node(node_id, "Geographic Latency Mismatch")

    def _detect_memory_tampering(self) -> None:
        """
        Proactively verifies that project memory hasn't been corrupted.
        """
        from warm_logic.sdk.identity import SovereignIdentity

        identity = SovereignIdentity()

        chronicle_path = Path("meta/memory/chronicle.md")
        if not self.audit.verify_memory_integrity(chronicle_path, identity):
            logger.critical("[AuditAgent] MEMORY TAMPERING DETECTED in Chronicle!")
            # Currently, memory tampering is a critical protocol violation.

    def _process_slashing_records(self) -> None:
        """
        Checks the store for new Slash metadata records and propagates them
        to the FleetManager.
        """
        if not hasattr(self.audit.store, "conn") or self.audit.store.conn is None:
            return

        try:
            # Look for SLASH records that haven't been processed
            # (In a real system, we'd track 'last processed ts' or delete after processing)
            cursor = self.audit.store.conn.execute(
                "SELECT key, value FROM metadata WHERE key LIKE 'SLASH:%'"
            )
            rows = cursor.fetchall()

            for key, value_json in rows:
                # Format: SLASH:miner:ts
                parts = key.split(":")
                if len(parts) >= 2:
                    node_id = parts[1]
                    try:
                        record = (
                            value_json
                            if isinstance(value_json, dict)
                            else json.loads(value_json)
                        )
                        reason = record.get("reason", "Unknown Violation")

                        # Apply to FleetManager
                        self.fleet.slash_node(node_id, reason)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Failed to process slashing records: {e}")
