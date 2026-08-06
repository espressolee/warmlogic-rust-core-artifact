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
PeerManager: Tracks active WarmLogic nodes in the local mesh.
Handles TTL-based expiry for inactive peers.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PeerInfo:
    """Represents a discovered peer node."""

    node_id: str
    http_port: int
    address: str
    last_seen: float = field(default_factory=time.time)

    def is_alive(self, ttl_seconds: float = 15.0) -> bool:
        return (time.time() - self.last_seen) < ttl_seconds


class PeerManager:
    """
    Manages the registry of discovered peers.
    Thread-safe with automatic TTL-based cleanup.
    """

    def __init__(self, ttl_seconds: float = 15.0):
        self._peers: Dict[str, PeerInfo] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._local_id: Optional[str] = None

    def set_local_id(self, node_id: str) -> None:
        """Set the local node's ID to filter self-discovery."""
        self._local_id = node_id

    def register_peer(self, node_id: str, address: str, http_port: int) -> None:
        """Register or update a peer."""
        if node_id == self._local_id:
            return  # Ignore self

        with self._lock:
            if node_id in self._peers:
                self._peers[node_id].last_seen = time.time()
                self._peers[node_id].address = address
                self._peers[node_id].http_port = http_port
            else:
                self._peers[node_id] = PeerInfo(
                    node_id=node_id, http_port=http_port, address=address
                )
                print(
                    f"[Mesh] New peer discovered: {node_id[:16]}... @ {address}:{http_port}"
                )

    def get_active_peers(self) -> List[PeerInfo]:
        """Returns list of peers that are still alive (within TTL)."""
        self._cleanup()
        with self._lock:
            return [p for p in self._peers.values() if p.is_alive(self._ttl)]

    def get_peer_count(self) -> int:
        """Returns count of active peers."""
        return len(self.get_active_peers())

    def _cleanup(self) -> None:
        """Remove expired peers."""
        with self._lock:
            expired = [k for k, v in self._peers.items() if not v.is_alive(self._ttl)]
            for k in expired:
                del self._peers[k]
                print(f"[Mesh] Peer expired: {k[:16]}...")
