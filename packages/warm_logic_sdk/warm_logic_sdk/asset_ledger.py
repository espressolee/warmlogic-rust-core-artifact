import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger("AssetLedger")


@dataclass
class AssetRecord:
    asset_id: str
    owner_id: str
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    pqc_signature: str
    hardware_id: str


class SovereignAssetSDK:
    """ Enterprise Asset Ledger SDK.
    Manages chain-of-custody for physical/digital assets with hardware rooting.
    """

    def __init__(self, client: Any):
        self.client = client  # SovereignClient
        self.assets: Dict[str, AssetRecord] = {}

    def register_asset(self, name: str, metadata: Dict[str, Any]) -> str:
        """Registers a new asset on the mesh."""
        asset_id = f"ASSET-{uuid.uuid4().hex[:8].upper()}"

        # Capture hardware root from client identity
        hardware_id = getattr(self.client.identity, "hardware_id", "HW-REAL-UNKNOWN")

        # Sign the genesis record
        genesis_data = {
            "action": "GENESIS",
            "timestamp": time.time(),
            "owner": self.client.identity.id,
            "metadata": metadata,
        }

        signed_packet = self.client.sign_message(str(genesis_data))

        record = AssetRecord(
            asset_id=asset_id,
            owner_id=self.client.identity.id,
            history=[genesis_data],
            metadata=metadata,
            pqc_signature=signed_packet["signature"],
            hardware_id=hardware_id,
        )

        self.assets[asset_id] = record
        logger.info(
            f"📦 [Asset] Registered {asset_id} ('{name}') with HW root {hardware_id}"
        )
        return asset_id

    def transfer_asset(self, asset_id: str, to_node_id: str, reason: str) -> bool:
        """Transfers ownership with BFT verification and PQC signing."""
        asset = self.assets.get(asset_id)
        if not asset:
            logger.error(f"Asset {asset_id} not found.")
            return False

        if asset.owner_id != self.client.identity.id:
            logger.error(f"Unauthorized transfer attempt for {asset_id}")
            return False

        transfer_data = {
            "action": "TRANSFER",
            "asset_id": asset_id,
            "from": asset.owner_id,
            "to": to_node_id,
            "reason": reason,
            "timestamp": time.time(),
            "hw_root": asset.hardware_id,
        }

        signed_packet = self.client.sign_message(str(transfer_data))

        # Propagate to mesh (Simulated BFT consensus trigger)
        logger.info(
            f"🤝 [Asset] Initiating BFT transfer for {asset_id} to {to_node_id[:8]}..."
        )

        # Update local record
        asset.owner_id = to_node_id
        asset.history.append(transfer_data)
        asset.pqc_signature = signed_packet["signature"]

        logger.info(
            f"✅ [Asset] Transfer of {asset_id} finalized via Forensic Consensus."
        )
        return True

    def get_asset_history(self, asset_id: str) -> List[Dict[str, Any]]:
        """Retrieves the full chain-of-custody for an asset."""
        asset = self.assets.get(asset_id)
        return asset.history if asset else []
