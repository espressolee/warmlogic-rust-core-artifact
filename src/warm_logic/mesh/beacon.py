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
Beacon: UDP-based local mesh discovery.
Broadcasts presence and listens for other nodes.
"""

import json
import random
import socket
import threading
import time
from typing import Optional

from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey

from .peers import PeerManager

BEACON_PORT = 8999
BROADCAST_INTERVAL = 2.0  # Faster for simulation


class Beacon:
    """
    UDP Beacon for local-first mesh discovery.
    Broadcasts node presence and listens for peers.
    """

    def __init__(
        self,
        node_id: str,
        http_port: int,
        peer_manager: PeerManager,
        beacon_port: int = BEACON_PORT,
    ):
        self.node_id = node_id
        self.http_port = http_port
        self.peer_manager = peer_manager
        self.beacon_port = beacon_port

        self._running = False
        self._broadcast_thread: Optional[threading.Thread] = None
        self._listen_thread: Optional[threading.Thread] = None

        # Set local ID in peer manager to filter self-discovery
        self.peer_manager.set_local_id(node_id)

    def start(self) -> None:
        """Start the beacon broadcast and listener threads."""
        if self._running:
            return

        self._running = True

        self._broadcast_thread = threading.Thread(
            target=self._broadcast_loop, daemon=True, name="Beacon-Broadcast"
        )
        self._listen_thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="Beacon-Listen"
        )

        self._broadcast_thread.start()
        self._listen_thread.start()
        print(f"[Beacon] Started on UDP:{self.beacon_port}")

    def stop(self) -> None:
        """Stop the beacon."""
        self._running = False
        print("[Beacon] Stopped")

    def _broadcast_loop(self) -> None:
        """Periodically broadcast presence to the local network."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)

        payload = json.dumps(
            {"type": "beacon", "node_id": self.node_id, "http_port": self.http_port}
        ).encode("utf-8")

        while self._running:
            try:
                sock.sendto(payload, ("<broadcast>", self.beacon_port))
            except Exception as e:
                print(f"[Beacon] Broadcast error: {e}")
            time.sleep(BROADCAST_INTERVAL)

        sock.close()

    def _listen_loop(self) -> None:
        """Listen for beacon packets from other nodes."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass

        try:
            sock.bind(("", self.beacon_port))
        except OSError as e:
            print(f"[Beacon] Failed to bind listener: {e}")
            return

        sock.settimeout(1.0)

        while self._running:
            try:
                data, addr = sock.recvfrom(1024)
                self._handle_packet(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[Beacon] Listen error: {e}")

        sock.close()

    def _handle_packet(self, data: bytes, addr: tuple) -> None:
        """Process a received beacon packet."""
        cm = ChaosMonkey()
        if cm.enabled:
            # 1. Drop
            if random.random() < cm.drop_rate:
                return

            # 2. Latency
            from warm_logic.mesh.topology import NetworkTopology

            total_latency = cm.latency_ms + NetworkTopology.get_latency(
                self.node_id.encode(), addr[0].encode()
            )
            if total_latency > 0:
                time.sleep(total_latency / 1000.0)

            # 3. Corruption
            if random.random() < cm.corruption_rate:
                data = b"CORRUPTED" + data[9:]

        try:
            payload = json.loads(data.decode("utf-8"))
            if payload.get("type") == "beacon":
                node_id = payload["node_id"]
                http_port = payload["http_port"]
                self.peer_manager.register_peer(node_id, addr[0], http_port)
        except (json.JSONDecodeError, KeyError):
            pass  # Ignore malformed packets
