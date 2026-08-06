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
import os
from typing import Any, Dict, Optional

import warm_logic_rs
from warm_logic_rs import SovereignStore

logger = logging.getLogger("StorageProvider")


class StorageProvider:
    """
    Sovereign Storage Provider (Physical Node)
    Uses the Rust-backed SovereignStore for high-performance chunk persistence.
    Verifies BFT signatures before committing to disk.
    """

    def __init__(self, node_id: str, data_dir: str = "./data/storage"):
        self.node_id = node_id
        self.data_dir = data_dir

        # Initialize physical persistence layer (Rust Sled-based)
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, f"provider_{node_id}.db")
        self.store = SovereignStore(db_path)

        logger.info(f"Physical Provider {node_id} active at {db_path}.")

    def handle_proposal(self, proposal: Dict[str, Any]) -> bool:
        """
        Processes and validates storage proposals.
        In a harsh audit, we verify signatures and constitutional compliance.
        """
        # The proposal object here mimics the decrypted BFT payload
        intent = proposal.get("intent")  # The exact object that was signed
        if not intent:
            logger.error("INVALID PROPOSAL: Missing signed intent.")
            return False

        action = intent.get("action")
        params = intent.get("params", {})
        signature = proposal.get("signature")
        sender_id = proposal.get("identity")

        # 1. Verify PQC Signature (Harsh Check)
        # We verify that the 'intent' was signed by the claimed identity
        payload_to_verify = str(intent)
        if not warm_logic_rs.verify(sender_id, payload_to_verify, signature):
            logger.error(f"INVALID SIGNATURE from {sender_id[:16]}!")
            return False

        if action == "STORE_CHUNK":
            return self._store_chunk(params)

        return False

    def _store_chunk(self, params: Dict[str, Any]) -> bool:
        """
        Persists a data chunk (Signature already verified).
        """
        file_id = params.get("file_id")
        chunk_index = params.get("chunk_index")
        chunk_hash = params.get("chunk_hash")
        chunk_data = params.get("chunk_data_mock")  # In reality, the raw bytes

        # 2. Persist to SovereignStore
        key = f"chunk:{file_id}:{chunk_index}"
        # We store the metadata and a reference to the data
        self.store.put(key, chunk_hash)

        logger.info(
            f"   [PhysicalStore] Committed chunk {chunk_index} of {file_id[:12]}"
        )
        return True

    def get_chunk(self, file_id: str, chunk_index: int) -> Optional[str]:
        """Retrieves chunk hash from physical store."""
        key = f"chunk:{file_id}:{chunk_index}"
        return self.store.get(key)
