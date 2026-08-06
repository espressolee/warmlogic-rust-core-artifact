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
SocialSyncAgent: Background gossip protocol for social feed synchronization.
Periodically pulls messages from random peers and merges into local store.
"""

import random
import threading
import time
from typing import TYPE_CHECKING, Optional

import requests

from .peers import PeerManager

if TYPE_CHECKING:
    from warm_logic.social.store import SocialStore

SYNC_INTERVAL = 3.0  # seconds between sync attempts
SYNC_TIMEOUT = 5.0  # HTTP request timeout


class SocialSyncAgent:
    """
    Background agent for gossip-based social feed synchronization.
    Randomly selects peers and merges their messages into the local store.
    """

    def __init__(self, peer_manager: PeerManager, social_store: "SocialStore") -> None:
        self.peer_manager = peer_manager
        self.social_store = social_store

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sync_count = 0
        self._last_sync_peer: Optional[str] = None

    def start(self) -> None:
        """Start the background sync thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._sync_loop, daemon=True, name="SocialSync"
        )
        self._thread.start()
        print("[Sync] Social gossip agent started")

    def stop(self) -> None:
        """Stop the sync agent."""
        self._running = False
        print("[Sync] Social gossip agent stopped")

    def get_stats(self) -> dict:
        """Get sync statistics for UI display."""
        return {
            "sync_count": self._sync_count,
            "last_peer": self._last_sync_peer,
            "active_peers": self.peer_manager.get_peer_count(),
        }

    def _sync_loop(self) -> None:
        """Main sync loop - periodically pull from random peers."""
        while self._running:
            time.sleep(SYNC_INTERVAL)

            peers = self.peer_manager.get_active_peers()
            if not peers:
                continue

            # Select random peer
            peer = random.choice(peers)
            self._last_sync_peer = peer.node_id[:16]

            try:
                self._sync_from_peer(peer.address, peer.http_port)
                self._sync_count += 1
            except Exception as e:
                print(f"[Sync] Error syncing from {peer.node_id[:16]}...: {e}")

    def _sync_from_peer(self, address: str, port: int) -> None:
        """Fetch and merge messages from a specific peer."""
        # Chaos Monkey Injection
        from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey

        cm = ChaosMonkey()
        if cm.enabled:
            # 1. Drop Request (Simulate network failure)
            if random.random() < cm.drop_rate:
                # print(f"[Sync-Chaos] Dropped sync request to {address}:{port}")
                raise Exception("ChaosMonkey: Network Drop")

            # 2. Latency
            # Topology Logic - Default to 0 when node IDs unavailable
            # Note: Full topology latency requires both source/dest node IDs
            topo_latency = 0  # Default: no additional topology latency

            # Combine Chaos Latency + Topology Latency
            total_latency_ms = cm.latency_ms + topo_latency

            if total_latency_ms > 0:
                time.sleep(total_latency_ms / 1000.0)

        url = f"http://{address}:{port}/api/social/feed"

        response = requests.get(url, timeout=SYNC_TIMEOUT)
        response.raise_for_status()

        messages = response.json()
        new_count = 0

        for msg_data in messages:
            # Reconstruct SovereignMessage and attempt to add
            from warm_logic.social.protocol import SovereignMessage

            try:
                msg = SovereignMessage(
                    sender_id=msg_data["sender_id"],
                    content=msg_data["content"],
                    signature=msg_data["signature"],
                    timestamp=msg_data["timestamp"],
                )

                # add_message handles deduplication and verification
                if self.social_store.add_message(msg):
                    new_count += 1
            except Exception:
                continue  # Skip malformed messages

        if new_count > 0:
            print(f"[Sync] Merged {new_count} new messages from peer")
