"""
Sovereign SDK
The primary interface for external applications to interact with the WarmLogic mesh.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from warm_logic.kernel.mesh.dht import Contact, SovereignDHT

logger = logging.getLogger("SovereignSDK")


class SovereignSDK:
    """
    A lightweight wrapper for connecting to and interacting with a WarmLogic mesh.
    """

    def __init__(
        self, node_id: bytes, host: str, port: int, public_key: Optional[bytes] = None
    ):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.public_key = public_key
        self.dht = SovereignDHT(node_id, host, port, public_key=public_key)
        self.running = False

    async def connect(self, bootstrap_seeds: List[Tuple[str, int]]):
        """Joins the mesh network."""
        logger.info(f"Connecting to WarmLogic Mesh via {len(bootstrap_seeds)} seeds...")
        await self.dht.start(enable_nat_discovery=False)
        await self.dht.bootstrap(bootstrap_seeds)
        self.running = True
        logger.info("✅ Connected to Mesh.")

    async def disconnect(self):
        """Gracefully shuts down the SDK connection."""
        if self.dht.transport:
            self.dht.transport.close()
        self.running = False
        logger.info("Disconnected from Mesh.")

    async def find_peers(self, target_id: bytes) -> List[Contact]:
        """Finds nodes closest to the target_id in the mesh."""
        if not self.running:
            raise RuntimeError("SDK not connected to mesh.")
        return await self.dht.iterative_find_node(target_id)

    async def submit_task(
        self, task_type: str, payload: Dict[str, Any], target_peer: Contact = None
    ):
        """
        Submits a task to the mesh.
        """
        import json

        message = {
            "type": "TASK_SUBMISSION",
            "task_type": task_type,
            "payload": payload,
            "sender_id": self.node_id.hex(),
        }

        if target_peer:
            self.dht.send(target_peer, json.dumps(message).encode("utf-8"))
        else:
            self.dht.broadcast(json.dumps(message).encode("utf-8"))

        logger.info(f"Task '{task_type}' submitted to mesh.")

    def get_status(self) -> Dict[str, Any]:
        """Returns the current state of the SDK connection."""
        return {
            "node_id": self.node_id.hex(),
            "address": f"{self.host}:{self.port}",
            "is_running": self.running,
            "known_neighbors": len(self.dht.routing.get_all_contacts()),
        }
