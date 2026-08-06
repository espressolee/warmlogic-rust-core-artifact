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
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from warm_logic.kernel.hardware.confidential import AttestationReport

logger = logging.getLogger("FleetManager")


@dataclass
class FleetNode:
    node_id: str
    last_seen: float
    report: Optional[AttestationReport]
    status: str = "UNKNOWN"  # VERIFIED, UNTRUSTED, OFFLINE, SLASHED


class FleetManager:
    """
    Production Armor - Fleet Manager.
    Orchestrates attestation and health for a distributed fleet of Trinity nodes.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, FleetNode] = {}
        self.health_threshold = 60.0  # seconds
        # Global Invariants Cache
        self.global_policies: Dict[str, Any] = {}

    def register_node(self, node_id: str, report: AttestationReport) -> None:
        """Register or update a node with its hardware attestation report."""
        status = "VERIFIED" if self._verify_node_report(report) else "UNTRUSTED"
        self.nodes[node_id] = FleetNode(
            node_id=node_id, last_seen=time.time(), report=report, status=status
        )
        logger.info(
            f"NODE_REGISTERED: {node_id} (Provider: {report.provider}, Status: {status})"
        )

    def _verify_node_report(self, report: AttestationReport) -> bool:
        """Internal verification logic for remote reports."""
        # Accept both KINETIC_TPM and KINETIC_ID providers
        valid_prefixes = ("KINETIC_TPM", "KINETIC_ID")
        if not any(report.provider.startswith(p) for p in valid_prefixes):
            return False
        if "REJECTION" in report.quote:
            return False
        return True

    def get_fleet_health(self) -> Dict[str, Any]:
        """Returns the aggregate health status of the fleet."""
        now = time.time()
        counts = {"VERIFIED": 0, "UNTRUSTED": 0, "OFFLINE": 0, "SLASHED": 0}

        for node in self.nodes.values():
            if (
                node.status != "SLASHED"
                and now - node.last_seen > self.health_threshold
            ):
                node.status = "OFFLINE"
            counts[node.status] += 1

        return {
            "total_nodes": len(self.nodes),
            "counts": counts,
            "healthy": (
                counts["VERIFIED"] > (len(self.nodes) / 2) if self.nodes else False
            ),
        }

    def heartbeat(self, node_id: str) -> None:
        """Update last seen for a node."""
        if node_id in self.nodes:
            self.nodes[node_id].last_seen = time.time()
            # Slashed nodes do not recover via heartbeat
            if self.nodes[node_id].status == "OFFLINE":
                self.nodes[node_id].status = "VERIFIED"

    def slash_node(self, node_id: str, reason: str) -> None:
        """
        Permanently isolate a node for misconduct.
        """
        if node_id in self.nodes:
            self.nodes[node_id].status = "SLASHED"
            logger.critical(f"NODE_SLASHED: {node_id} | Reason: {reason}")
        else:
            # Create a placeholder for the slashed node if not known
            self.nodes[node_id] = FleetNode(
                node_id=node_id, last_seen=0.0, report=None, status="SLASHED"
            )
            logger.critical(f"STRANGER_SLASHED: {node_id} | Reason: {reason}")

    def sync_global_policy(self, invariant_id: str, state: Any) -> None:
        """
        Synchronize a global policy invariant.
        """
        self.global_policies[invariant_id] = state
        logger.warning(f"[Hive] Global Policy Sync: {invariant_id} -> {state}")

    def get_policy_status(self) -> Dict[str, Any]:
        """Returns the current state of all global invariants."""
        return self.global_policies
