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
Network Pillar
P2P Mesh Networking and Discovery.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

from warm_logic.kernel.mesh.dht import SovereignDHT
from warm_logic.kernel.sys.cryptography import MLDSA


class MeshNetworking:
    """
    Manages peer connections and message propagation using Sovereign DHT.
    Bound to PQC Identity.
    """

    def __init__(
        self,
        node_id: Optional[bytes] = None,
        address: str = "127.0.0.1",
        port: int = 4000,
    ):
        # Derive Node ID from PQC Public Key if not provided
        if not node_id:
            mldsa = MLDSA()
            keys = mldsa.generate_keypair()
            node_id = hashlib.sha3_256(keys.public_key.encode()).digest()

        self.dht = SovereignDHT(node_id, address, port)

    async def ignite(self, bootstrap_seeds: List[tuple[str, int]]) -> None:
        """Initializes the mesh network."""
        await self.dht.start()
        await self.dht.bootstrap(bootstrap_seeds)

    def broadcast(self, message: bytes) -> int:
        """Broadcasts a message to the mesh via DHT gossip."""
        # DHT-based gossip: Send to K closest neighbors
        # and rely on them to propagate.
        neighbors = self.dht.routing.find_neighbors(self.dht.node_id)
        count = 0
        for peer in neighbors:
            # hardware attestation enforcement: Reactive P2P Broadcast
            self.dht.send(peer, message)
            count += 1
        return count

    from typing import Any

    def get_mesh_status(self) -> Dict[str, Any]:
        """Returns the health of the sovereign mesh."""
        # hardware attestation enforcement: No more hardcoded truth.
        neighbors = self.dht.routing.find_neighbors(self.dht.node_id)

        # Check if any neighbor is actually PQC bound (has a public key)
        pqc_valid = (
            all(n.public_key is not None for n in neighbors) if neighbors else False
        )

        return {
            "node_id": self.dht.node_id.hex(),
            "peer_count": len(neighbors),
            "is_sovereign": len(neighbors)
            > 0,  # If we have neighbors, we are part of the sovereign mesh
            "pqc_bound": pqc_valid,
        }
