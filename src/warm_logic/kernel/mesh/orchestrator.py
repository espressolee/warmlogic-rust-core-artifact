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
import asyncio
import logging
from typing import Any, Dict

from warm_logic.kernel.intelligence.swarm_orchestrator import SwarmOrchestrator

logger = logging.getLogger("FleetOrchestrator")


class FleetOrchestrator:
    """
    root authority-level strategic management.
    Periodically polls edge nodes for sensor summaries and dictates high-level goals.
    """

    def __init__(self, mesh_client: Any, bft_engine: Any):
        self.mesh = mesh_client
        self.orchestrator = SwarmOrchestrator(mesh_client, bft_engine)
        self.fleet_status: Dict[str, Dict[str, Any]] = {}

    async def run_strategic_loop(self):
        """
        The main loop for strategic fleet oversight.
        """
        logger.info("[root authority] Strategic command loop active.")
        while True:
            await self.update_fleet_map()
            await self.issue_strategic_directives()
            await asyncio.sleep(60)  # Poll every minute

    async def update_fleet_map(self):
        """
        Refreshes the internal map of node capabilities and health.
        """
        all_contacts = self.mesh.routing.get_all_contacts()
        for contact in all_contacts:
            node_id = contact.node_id.hex()
            self.fleet_status[node_id] = {
                "address": f"{contact.address}:{contact.port}",
                "capabilities": contact.capabilities or {},
                "last_seen": getattr(contact, "last_seen", 0),
            }
        logger.debug(
            f"🦅 [root authority] Fleet map updated. {len(self.fleet_status)} nodes tracked."
        )

    async def issue_strategic_directives(self):
        """
        Heuristic: If we see sensor nodes but no reports, issue an analysis goal.
        """
        sensor_nodes = [
            nid
            for nid, status in self.fleet_status.items()
            if status["capabilities"].get("SENSOR_STREAM", 0) >= 80
        ]

        if sensor_nodes:
            logger.info(
                f"🦅 [root authority] Detected {len(sensor_nodes)} edge sensor nodes. Issuing Analysis Directive."
            )
            plan_id = self.orchestrator.submit_goal(
                "Analyze system sensor telemetry for anomalies"
            )
            logger.info(f"[root authority] Strategic Plan Issued: {plan_id}")

    def get_fleet_report(self) -> Dict[str, Any]:
        """Returns a summary of the current fleet configuration."""
        return {
            "total_nodes": len(self.fleet_status),
            "root authority_id": self.mesh.node_id.hex(),
            "nodes": self.fleet_status,
        }
