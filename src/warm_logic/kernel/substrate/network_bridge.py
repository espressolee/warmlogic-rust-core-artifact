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
Network Bridge
Integrates Rust UDP transport, DHT mesh, Gossip protocol, and StitchServer.

This module connects:
- Rust NetworkingEngine (UDP transport layer)
- Python GossipAgent (manifest propagation)
- StitchServer (HTTP/SSE gateway)
- BFT Consensus (block propagation)
"""

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("NetworkBridge")


@dataclass
class NetworkMessage:
    """Unified message format for network communication."""

    msg_type: str  # MANIFEST_ANNOUNCE, BLOCK_PROPOSE, VOTE, SYNC_MANIFEST, VETO_SIGNAL
    sender_id: str
    payload: Dict[str, Any]
    timestamp: float
    signature: Optional[str] = None


class MessageRouter:
    """
    Routes incoming network messages to appropriate handlers.
    Connects UDP transport → Protocol Handlers → StitchServer broadcast.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[NetworkMessage], None]]] = {}
        self._lock = threading.Lock()
        self._stats = {
            "messages_received": 0,
            "messages_routed": 0,
            "unknown_types": 0,
            "handler_errors": 0,
        }

    def register_handler(
        self, msg_type: str, handler: Callable[[NetworkMessage], None]
    ) -> None:
        """Register a handler for a specific message type."""
        with self._lock:
            if msg_type not in self._handlers:
                self._handlers[msg_type] = []
            self._handlers[msg_type].append(handler)
            logger.info(f"[Router] Registered handler for {msg_type}")

    def route(self, raw_data: bytes, source_addr: str) -> None:
        """Parse and route incoming message."""
        self._stats["messages_received"] += 1

        try:
            # Parse JSON message
            data = json.loads(raw_data.decode("utf-8"))

            msg = NetworkMessage(
                msg_type=data.get("type", "UNKNOWN"),
                sender_id=data.get("sender_id", "unknown"),
                payload=data,
                timestamp=data.get("timestamp", time.time()),
                signature=data.get("signature"),
            )

            # Route to handlers
            with self._lock:
                handlers = self._handlers.get(msg.msg_type, [])

            if not handlers:
                self._stats["unknown_types"] += 1
                logger.debug(f"[Router] No handler for message type: {msg.msg_type}")
                return

            for handler in handlers:
                try:
                    handler(msg)
                    self._stats["messages_routed"] += 1
                except Exception as e:
                    self._stats["handler_errors"] += 1
                    logger.error(f"[Router] Handler error for {msg.msg_type}: {e}")

        except json.JSONDecodeError as e:
            logger.warning(f"[Router] Invalid JSON from {source_addr}: {e}")
        except Exception as e:
            logger.error(f"[Router] Route error: {e}")

    def get_stats(self) -> Dict[str, int]:
        """Get routing statistics."""
        return self._stats.copy()


class NetworkBridge:
    """
    Central network integration hub.
    Connects all network components for multi-node operation.
    """

    def __init__(
        self,
        node_id: str,
        bind_addr: str = "0.0.0.0",
        bind_port: int = 9000,
    ) -> None:
        self.node_id = node_id
        self.bind_addr = bind_addr
        self.bind_port = bind_port

        self.router = MessageRouter()
        self._rust_dht: Optional[Any] = None
        self._gossip_agent: Optional[Any] = None
        self._stitch_server: Optional[Any] = None
        self._bft_engine: Optional[Any] = None
        self._propagator: Optional[Any] = None

        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._poll_interval: float = 0.01  # 10ms polling interval

        # Known peers
        self._peers: Dict[str, Dict[str, Any]] = {}
        self._peer_lock = threading.Lock()

        self._setup_default_handlers()

    def start(self) -> bool:
        """
        Start the network bridge polling loop.
        This continuously polls the Rust DHT for incoming messages and routes them.
        """
        if self._running:
            logger.warning("[Bridge] Already running")
            return False

        if not self._rust_dht:
            if not self.connect_rust_dht():
                logger.error("[Bridge] Cannot start without Rust DHT")
                return False

        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.info(f"[Bridge] Started polling loop (interval={self._poll_interval}s)")
        return True

    def stop(self) -> None:
        """Stop the network bridge polling loop."""
        if not self._running:
            return

        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=2.0)
            self._poll_thread = None
        logger.info("[Bridge] Stopped polling loop")

    def _poll_loop(self) -> None:
        """
        Background thread that polls Rust DHT for incoming messages.
        Routes messages through the MessageRouter to appropriate handlers.
        """
        while self._running:
            try:
                if self._rust_dht:
                    # Poll for incoming UDP messages from Rust transport
                    messages = self._rust_dht.poll_messages()
                    for source_addr, payload in messages:
                        self.router.route(bytes(payload), source_addr)
            except Exception as e:
                logger.error(f"[Bridge] Poll error: {e}")

            time.sleep(self._poll_interval)

    def _setup_default_handlers(self) -> None:
        """Set up default message handlers."""
        # Manifest announcements (Gossip)
        self.router.register_handler("MANIFEST_ANNOUNCE", self._handle_manifest)

        # Block proposals (BFT)
        self.router.register_handler("BLOCK_PROPOSE", self._handle_block_propose)

        # Votes (BFT)
        self.router.register_handler("VOTE", self._handle_vote)

        # Sync manifest (Propagation)
        self.router.register_handler("SYNC_MANIFEST", self._handle_sync_manifest)

        # Veto signal (Critical)
        self.router.register_handler("VETO_SIGNAL", self._handle_veto_signal)

        # Insight announcements (Evolution)
        self.router.register_handler("INSIGHT_ANNOUNCE", self._handle_insight)

        # Delta sync (Propagation)
        self.router.register_handler("DELTA_REQUEST", self._handle_delta_request)
        self.router.register_handler("DELTA_RESPONSE", self._handle_delta_response)

    def connect_rust_dht(self) -> bool:
        """Initialize Rust DHT network layer."""
        try:
            import warm_logic_rs

            self._rust_dht = warm_logic_rs.RustDHT(self.node_id)
            self._rust_dht.start(self.bind_addr, self.bind_port)

            logger.info(
                f"[Bridge] Rust DHT connected at {self.bind_addr}:{self.bind_port}"
            )
            return True

        except ImportError:
            logger.warning("[Bridge] Rust core not available, using Python fallback")
            return False
        except Exception as e:
            logger.error(f"[Bridge] Failed to connect Rust DHT: {e}")
            return False

    def connect_gossip(self, gossip_agent: Any) -> None:
        """Connect GossipAgent for manifest propagation."""
        self._gossip_agent = gossip_agent
        logger.info("[Bridge] GossipAgent connected")

    def connect_stitch(self, stitch_server: Any) -> None:
        """Connect StitchServer for SSE broadcasting."""
        self._stitch_server = stitch_server
        logger.info("[Bridge] StitchServer connected")

    def connect_bft(self, bft_engine: Any) -> None:
        """Connect BFT consensus engine."""
        self._bft_engine = bft_engine
        logger.info("[Bridge] BFT Engine connected")

    def add_peer(
        self,
        peer_id: str,
        address: str,
        port: int,
        public_key: Optional[str] = None,
    ) -> None:
        """Add a known peer to the network."""
        with self._peer_lock:
            self._peers[peer_id] = {
                "id": peer_id,
                "address": address,
                "port": port,
                "public_key": public_key,
                "last_seen": time.time(),
            }

        # Update Rust DHT if available
        if self._rust_dht:
            try:
                self._rust_dht.update(peer_id, address, port)
            except Exception as e:
                logger.warning(f"[Bridge] Failed to update Rust DHT: {e}")

        logger.info(f"[Bridge] Added peer {peer_id[:8]}... at {address}:{port}")

    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer from the network."""
        with self._peer_lock:
            if peer_id in self._peers:
                del self._peers[peer_id]
                logger.info(f"[Bridge] Removed peer {peer_id[:8]}...")

    def get_peers(self) -> List[Dict[str, Any]]:
        """Get list of known peers."""
        with self._peer_lock:
            return list(self._peers.values())

    def broadcast(self, msg_type: str, payload: Dict[str, Any]) -> int:
        """
        Broadcast a message to all known peers.
        Returns number of peers notified.
        """
        message = {
            "type": msg_type,
            "sender_id": self.node_id,
            "payload": payload,
            "timestamp": time.time(),
        }

        raw_data = json.dumps(message).encode("utf-8")

        # Also broadcast via StitchServer SSE
        if self._stitch_server:
            try:
                from warm_logic.kernel.substrate.stitch_server import StitchServer

                StitchServer.broadcast(f"network_{msg_type.lower()}", payload)
            except Exception as e:
                logger.warning(f"[Bridge] StitchServer broadcast failed: {e}")

        # Send via Rust UDP
        count = 0
        with self._peer_lock:
            for peer in self._peers.values():
                try:
                    if self._rust_dht:
                        self._rust_dht.send(peer["address"], peer["port"], raw_data)
                    count += 1
                except Exception as e:
                    logger.debug(f"[Bridge] Send to {peer['id'][:8]}... failed: {e}")

        return count

    def send_to_peer(
        self,
        peer_id: str,
        msg_type: str,
        payload: Dict[str, Any],
    ) -> bool:
        """Send a message to a specific peer."""
        with self._peer_lock:
            peer = self._peers.get(peer_id)

        if not peer:
            logger.warning(f"[Bridge] Unknown peer: {peer_id[:8]}...")
            return False

        message = {
            "type": msg_type,
            "sender_id": self.node_id,
            "payload": payload,
            "timestamp": time.time(),
        }

        raw_data = json.dumps(message).encode("utf-8")

        try:
            if self._rust_dht:
                self._rust_dht.send(peer["address"], peer["port"], raw_data)
                return True
        except Exception as e:
            logger.error(f"[Bridge] Send to {peer_id[:8]}... failed: {e}")

        return False

    # --- Message Handlers ---

    def _handle_manifest(self, msg: NetworkMessage) -> None:
        """Handle MANIFEST_ANNOUNCE from gossip."""
        if self._gossip_agent:
            self._gossip_agent.on_receive_manifest(
                sender_id=msg.sender_id,
                manifest_hash=msg.payload.get("manifest_hash", ""),
                timestamp=msg.timestamp,
                signature=msg.signature,
                sender_pk_hex=msg.payload.get("sender_pk"),
            )

        # Broadcast via SSE
        self._broadcast_sse(
            "manifest_received",
            {
                "sender_id": msg.sender_id,
                "manifest_hash": msg.payload.get("manifest_hash"),
            },
        )

    def _handle_block_propose(self, msg: NetworkMessage) -> None:
        """Handle BLOCK_PROPOSE from BFT consensus."""
        if self._bft_engine:
            try:
                block_hash = msg.payload.get("block_hash", "")
                self._bft_engine.propose(block_hash)
                logger.info(f"[Bridge] Block proposed: {block_hash[:16]}...")
            except Exception as e:
                logger.error(f"[Bridge] Block propose failed: {e}")

        self._broadcast_sse(
            "block_proposed",
            {
                "block_hash": msg.payload.get("block_hash"),
                "proposer": msg.sender_id,
                "round": msg.payload.get("round"),
            },
        )

    def _handle_vote(self, msg: NetworkMessage) -> None:
        """Handle VOTE from BFT consensus."""
        if self._bft_engine:
            try:
                import warm_logic_rs

                vote = warm_logic_rs.Vote(
                    voter_id=msg.sender_id,
                    block_hash=msg.payload.get("block_hash", ""),
                    signature=msg.signature or "",
                )

                has_quorum = self._bft_engine.cast_vote(vote)

                if has_quorum:
                    logger.info(
                        f"[Bridge] Quorum reached for block: "
                        f"{msg.payload.get('block_hash', '')[:16]}..."
                    )
                    self._broadcast_sse(
                        "quorum_reached",
                        {
                            "block_hash": msg.payload.get("block_hash"),
                            "round": msg.payload.get("round"),
                        },
                    )

            except ImportError:
                logger.warning("[Bridge] Rust core not available for vote")
            except Exception as e:
                logger.error(f"[Bridge] Vote handling failed: {e}")

    def _handle_sync_manifest(self, msg: NetworkMessage) -> None:
        """Handle SYNC_MANIFEST for codebase synchronization."""
        logger.info(
            f"[Bridge] Sync manifest from {msg.sender_id[:8]}...: "
            f"{msg.payload.get('root_hash', '')[:16]}..."
        )

        # Delegate to propagation engine if available
        self._broadcast_sse(
            "sync_manifest",
            {
                "sender_id": msg.sender_id,
                "root_hash": msg.payload.get("root_hash"),
            },
        )

    def _handle_veto_signal(self, msg: NetworkMessage) -> None:
        """Handle VETO_SIGNAL - critical security event."""
        logger.warning(
            f"[Bridge] VETO SIGNAL from {msg.sender_id[:8]}...: "
            f"{msg.payload.get('reason', 'unknown')}"
        )

        # Broadcast immediately via SSE (priority)
        self._broadcast_sse(
            "veto_signal",
            {
                "sender_id": msg.sender_id,
                "reason": msg.payload.get("reason"),
                "insight": msg.payload.get("insight"),
            },
        )

    def _handle_insight(self, msg: NetworkMessage) -> None:
        """Handle INSIGHT_ANNOUNCE from evolution chamber."""
        if self._gossip_agent:
            self._gossip_agent.on_receive_insight(
                sender_id=msg.sender_id,
                insight=msg.payload.get("insight", {}),
                timestamp=msg.timestamp,
            )

        self._broadcast_sse(
            "insight_received",
            {
                "sender_id": msg.sender_id,
                "insight": msg.payload.get("insight"),
            },
        )

    def _handle_delta_request(self, msg: NetworkMessage) -> None:
        """Handle DELTA_REQUEST for codebase synchronization."""
        logger.info(
            f"[Bridge] Delta request from {msg.sender_id[:8]}... "
            f"for hash {msg.payload.get('target_hash', '')[:16]}..."
        )

        # Delegate to propagation engine if connected
        if hasattr(self, "_propagator") and self._propagator:
            response = self._propagator.on_receive_delta_request(msg.payload)
            if response:
                # Send response back to requester
                self.send_to_peer(msg.sender_id, "DELTA_RESPONSE", response)

        self._broadcast_sse(
            "delta_request",
            {
                "sender_id": msg.sender_id,
                "target_hash": msg.payload.get("target_hash"),
            },
        )

    def _handle_delta_response(self, msg: NetworkMessage) -> None:
        """Handle DELTA_RESPONSE with file patches."""
        logger.info(
            f"[Bridge] Delta response from {msg.sender_id[:8]}... "
            f"with {msg.payload.get('total_files', 0)} files"
        )

        # Delegate to propagation engine if connected
        if hasattr(self, "_propagator") and self._propagator:
            applied = self._propagator.on_receive_delta_response(msg.payload)
            logger.info(f"[Bridge] Applied {applied} files from delta response")

        self._broadcast_sse(
            "delta_response",
            {
                "sender_id": msg.sender_id,
                "total_files": msg.payload.get("total_files"),
                "target_hash": msg.payload.get("target_hash"),
            },
        )

    def connect_propagator(self, propagator: Any) -> None:
        """Connect SovereignPropagator for delta sync."""
        self._propagator = propagator
        logger.info("[Bridge] SovereignPropagator connected")

    def _broadcast_sse(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast event via StitchServer SSE."""
        if self._stitch_server:
            try:
                from warm_logic.kernel.substrate.stitch_server import StitchServer

                StitchServer.broadcast(event_type, data)
            except Exception as e:
                logger.debug(f"[Bridge] SSE broadcast failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get network bridge status."""
        return {
            "node_id": self.node_id,
            "bind_addr": self.bind_addr,
            "bind_port": self.bind_port,
            "running": self._running,
            "peer_count": len(self._peers),
            "rust_dht_connected": self._rust_dht is not None,
            "gossip_connected": self._gossip_agent is not None,
            "stitch_connected": self._stitch_server is not None,
            "bft_connected": self._bft_engine is not None,
            "propagator_connected": self._propagator is not None,
            "router_stats": self.router.get_stats(),
        }


class BlockPropagationHandler:
    """
    Handles block propagation between nodes.
    Registered with StitchServer for HTTP/POST reception.
    Integrates with BFT engine for consensus.
    """

    def __init__(
        self,
        bridge: NetworkBridge,
        ledger: Optional[Any] = None,
    ) -> None:
        self.bridge = bridge
        self.ledger = ledger
        self._pending_blocks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def handle_block(self, payload: Dict[str, Any]) -> None:
        """
        Handle incoming block from StitchServer POST.
        This is registered as a callback via StitchServer.register_handler().
        """
        block_hash = payload.get("block_hash", "")
        transactions = payload.get("transactions", [])
        proposer = payload.get("proposer", "")
        round_num = payload.get("round", 0)

        logger.info(
            f"[BlockHandler] Received block {block_hash[:16]}... "
            f"from {proposer[:8]}... (round {round_num})"
        )

        # Store pending block
        with self._lock:
            self._pending_blocks[block_hash] = {
                "hash": block_hash,
                "transactions": transactions,
                "proposer": proposer,
                "round": round_num,
                "received_at": time.time(),
            }

        # Forward to BFT engine via bridge
        self.bridge.router.route(
            json.dumps(
                {
                    "type": "BLOCK_PROPOSE",
                    "sender_id": proposer,
                    "block_hash": block_hash,
                    "transactions": transactions,
                    "round": round_num,
                }
            ).encode("utf-8"),
            f"{proposer}:0",
        )

    def handle_vote(self, payload: Dict[str, Any]) -> None:
        """
        Handle incoming vote from StitchServer POST.
        """
        block_hash = payload.get("block_hash", "")
        voter_id = payload.get("voter_id", "")
        signature = payload.get("signature", "")

        logger.info(
            f"[BlockHandler] Received vote from {voter_id[:8]}... "
            f"for block {block_hash[:16]}..."
        )

        # Forward to BFT engine via bridge
        self.bridge.router.route(
            json.dumps(
                {
                    "type": "VOTE",
                    "sender_id": voter_id,
                    "block_hash": block_hash,
                    "signature": signature,
                }
            ).encode("utf-8"),
            f"{voter_id}:0",
        )

    def get_pending_blocks(self) -> List[Dict[str, Any]]:
        """Get list of pending blocks awaiting consensus."""
        with self._lock:
            return list(self._pending_blocks.values())

    def clear_committed(self, block_hash: str) -> None:
        """Remove a committed block from pending."""
        with self._lock:
            if block_hash in self._pending_blocks:
                del self._pending_blocks[block_hash]


def register_block_handlers(
    bridge: NetworkBridge,
    stitch_server: Any,
    ledger: Optional[Any] = None,
) -> BlockPropagationHandler:
    """
    Register block propagation handlers with StitchServer.
    This enables multi-node block/vote propagation via HTTP/SSE.
    """
    from warm_logic.kernel.substrate.stitch_server import StitchServer

    handler = BlockPropagationHandler(bridge, ledger)

    # Register HTTP POST handlers
    StitchServer.register_handler("/block", handler.handle_block)
    StitchServer.register_handler("/vote", handler.handle_vote)

    logger.info("[Bridge] Block propagation handlers registered")

    return handler
