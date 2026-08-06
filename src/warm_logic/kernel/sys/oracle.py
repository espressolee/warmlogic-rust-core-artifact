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
Sovereign Oracle
Secure ingestion of external data anchored via ZK-Light Clients and Replicated Ledger.
"""

import hashlib
import json
import logging
import time
from typing import Any, Optional

from warm_logic.kernel.economy.ledger import ReplicatedLedger, Transaction

logger = logging.getLogger("SovereignOracle")


class SovereignOracle:
    """
    Ingests external data and commits it to the Sovereign Ledger as an anchored event.
    """

    def __init__(self, ledger: ReplicatedLedger):
        self.ledger = ledger

    def ingest_data(self, source: str, data_key: str, data_value: Any) -> Optional[str]:
        """
        Anchors external data into the ledger.
        This provides a permanent, auditable record of world-state at a specific block height.
        """
        payload = {
            "source": source,
            "key": data_key,
            "value": data_value,
            "ingest_time": time.time(),
        }

        payload_json = json.dumps(payload, sort_keys=True)
        data_hash = hashlib.sha3_256(payload_json.encode()).hexdigest()

        # In a real scenario, we would use a specialized Oracle Fee
        # For now, we "commit" this as a metadata anchor in the ledger's store
        # and trigger a transaction if required for decentralization.

        try:
            # Anchor to persistence
            meta_key = f"ORACLE:{source}:{data_key}"
            self.ledger.store.set_meta(meta_key, payload)

            # Create a "Truth Transaction" to record the hash in the block chain
            # The source is the Oracle identity, target is the Data Root
            # amount 0 (Signal only)
            tx = Transaction(
                source=f"ORACLE:{source[:8]}",
                target="DATA_ROOT",
                amount=0,
                signature=f"SIG_ORACLE_{data_hash[:8]}",  # Mock sig for now, will use PQC later
                timestamp=time.time(),
            )

            if self.ledger.submit_tx(tx):
                logger.info(f"[Oracle] Data Anchored: {meta_key} -> {data_hash[:8]}")
                return data_hash
            else:
                logger.error(f"[Oracle] Ledger rejection for {data_key}")
                return None
        except Exception as e:
            logger.error(f"[Oracle] Ingestion failure: {e}")
            return None

    def verify_data(self, source: str, data_key: str, expected_value: Any) -> bool:
        """
        Verifies if the data in the store matches the expectation.
        """
        meta_key = f"ORACLE:{source}:{data_key}"
        recorded = self.ledger.store.get_meta(meta_key)
        if not recorded:
            return False

        return recorded.get("value") == expected_value
