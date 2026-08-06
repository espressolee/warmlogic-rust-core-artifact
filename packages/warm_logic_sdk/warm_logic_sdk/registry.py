import logging
from typing import Any, Dict, List, Optional

from .client import SovereignClient

logger = logging.getLogger("SovereignRegistry")


class SovereignRegistry:
    """
    BFT-Backed Service Discovery for the Sovereign Marketplace.
    Allows clients to discover verified storage providers and other services.
    """

    def __init__(self, client: SovereignClient):
        self.client = client
        self._provider_cache: List[Dict[str, Any]] = []

    def register_storage_provider(
        self, endpoint: str, capacity_gb: int, credits_per_gb_day: float = 1.0
    ) -> Dict[str, Any]:
        """
        Registers the local node as a storage provider in the mesh.
        Requires BFT consensus for inclusion in the global registry.
        """
        logger.info(f"🌐 Registering Storage Provider at {endpoint}...")

        proposal = self.client.submit_proposal(
            action="REGISTER_STORAGE_PROVIDER",
            params={
                "endpoint": endpoint,
                "capacity_gb": capacity_gb,
                "credits_per_gb_day": credits_per_gb_day,
                "pqc_pubkey": self.client.identity.id,
                "service_type": "v1.storage.drive",
            },
        )

        return proposal

    def list_providers(
        self, service_type: str = "v1.storage.drive"
    ) -> List[Dict[str, Any]]:
        """
        Retrieves a list of verified providers from the Sovereign Ledger.
        In , this fetches from the BFT-synchronized state.
        """
        # For now, we simulate the retrieval from the BFT-backed 'Truth'
        # In a real implementation, this would call client.get_truth("marketplace.providers")
        logger.info(f"🔍 Discovering '{service_type}' providers...")

        # MOCK MESH FETCH
        mock_providers = [
            {"node_id": "SN-ALPHA-01", "endpoint": "10.0.0.5:9000", "capacity_gb": 100},
            {"node_id": "SN-BETA-02", "endpoint": "10.0.0.6:9000", "capacity_gb": 500},
        ]

        self._provider_cache = mock_providers
        return mock_providers

    def get_provider(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Returns metadata for a specific provider."""
        for p in self._provider_cache:
            if p["node_id"] == node_id:
                return p
        return None
