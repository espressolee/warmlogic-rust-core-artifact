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
Federation Network Transport

Async network transport layer for sovereign federation nodes.
Supports TCP with optional TLS and UDP for discovery.
"""

import asyncio
import logging
import ssl
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .protocol import (
    FederationMessage,
    HelloPayload,
    KeyExchangePayload,
    MessageBuilder,
    MessageType,
    ProtocolHeader,
)

logger = logging.getLogger("FederationTransport")

# Default ports
DEFAULT_TCP_PORT = 17300  # 
DEFAULT_UDP_PORT = 17301


class ConnectionState(Enum):
    """Connection lifecycle states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    HANDSHAKING = "handshaking"
    KEY_EXCHANGE = "key_exchange"
    ESTABLISHED = "established"
    CLOSING = "closing"


@dataclass
class PeerConnection:
    """Represents a connection to a peer node."""

    node_id: str
    host: str
    port: int
    state: ConnectionState = ConnectionState.DISCONNECTED
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    session_key: bytes = b""  # ML-KEM derived session key
    session_id: bytes = b""
    encapsulation_key: str = ""
    signing_key: str = ""
    last_seen: float = 0.0
    latency_ms: float = 0.0
    messages_sent: int = 0
    messages_received: int = 0

    def __post_init__(self) -> None:
        if self.last_seen == 0.0:
            self.last_seen = time.time()


@dataclass
class TransportConfig:
    """Transport layer configuration."""

    bind_host: str = "0.0.0.0"
    tcp_port: int = DEFAULT_TCP_PORT
    udp_port: int = DEFAULT_UDP_PORT
    max_connections: int = 64
    connection_timeout: float = 10.0
    heartbeat_interval: float = 30.0
    reconnect_delay: float = 5.0
    max_message_size: int = 1024 * 1024  # 1MB
    enable_tls: bool = False
    tls_cert_file: Optional[str] = None
    tls_key_file: Optional[str] = None


class FederationTransport:
    """
    Async Federation Transport Layer

    Handles network communication between sovereign federation nodes
    with PQC-protected channels.
    """

    def __init__(
        self,
        node_id: str,
        signing_key: str,
        encapsulation_key: str,
        decapsulation_key: str,
        signing_public_key: Optional[str] = None,
        config: Optional[TransportConfig] = None,
    ):
        self.node_id = node_id
        self.signing_key = signing_key  # Secret key for signing
        self.signing_public_key = signing_public_key or ""  # Public key for sharing
        self.encapsulation_key = encapsulation_key  # Public key for KEM
        self.decapsulation_key = decapsulation_key  # Secret key for KEM
        self.config = config or TransportConfig()

        # State
        self.peers: Dict[str, PeerConnection] = {}
        self.pending_connections: Set[str] = set()
        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._message_builder = MessageBuilder(node_id, signing_key)

        # Callbacks
        self._message_handlers: Dict[MessageType, Callable] = {}
        self._on_peer_connected: Optional[Callable] = None
        self._on_peer_disconnected: Optional[Callable] = None

        # Rust core
        self._rs = None

    def _get_rust_core(self) -> Any:
        """Lazy load Rust core."""
        if self._rs is None:
            from warm_logic.kernel import rust_loader

            if rust_loader.HAS_RUST_CORE:
                self._rs = rust_loader.load_rust_core()
        return self._rs

    # --- Server ---

    async def start_server(self) -> bool:
        """Start the federation server."""
        try:
            ssl_context = None
            if self.config.enable_tls and self.config.tls_cert_file:
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(
                    self.config.tls_cert_file, self.config.tls_key_file
                )

            self._server = await asyncio.start_server(
                self._handle_client,
                self.config.bind_host,
                self.config.tcp_port,
                ssl=ssl_context,
            )

            self._running = True
            logger.info(
                f"[Transport] Server started on {self.config.bind_host}:{self.config.tcp_port}"
            )

            # Start background tasks
            asyncio.create_task(self._heartbeat_loop())

            return True
        except Exception as e:
            logger.error(f"[Transport] Failed to start server: {e}")
            return False

    async def stop_server(self) -> None:
        """Stop the federation server."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Close all peer connections
        for peer in list(self.peers.values()):
            await self.disconnect_peer(peer.node_id)

        logger.info("[Transport] Server stopped")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming client connection."""
        peer_addr = writer.get_extra_info("peername")
        logger.info(f"[Transport] Incoming connection from {peer_addr}")

        try:
            # Read HELLO message
            msg = await self._read_message(reader)
            if not msg or msg.header.msg_type != MessageType.HELLO:
                logger.warning(
                    f"[Transport] Expected HELLO, got {msg.header.msg_type if msg else 'None'}"
                )
                writer.close()
                return

            # Parse HELLO
            hello = HelloPayload.unpack(msg.payload)
            logger.info(f"[Transport] HELLO from {hello.node_id}")

            # Create peer connection
            peer = PeerConnection(
                node_id=hello.node_id,
                host=peer_addr[0],
                port=peer_addr[1],
                state=ConnectionState.HANDSHAKING,
                reader=reader,
                writer=writer,
                encapsulation_key=hello.encapsulation_key,
                signing_key=hello.signing_key,
            )

            # Send HELLO_ACK (use public keys for sharing)
            ack = self._message_builder.build_hello(
                self.encapsulation_key, self.signing_public_key
            )
            ack.header.msg_type = MessageType.HELLO_ACK
            await self._send_message(writer, ack)

            # Perform key exchange
            if await self._server_key_exchange(peer):
                peer.state = ConnectionState.ESTABLISHED
                self.peers[peer.node_id] = peer

                if self._on_peer_connected:
                    await self._on_peer_connected(peer)

                # Start message loop
                await self._message_loop(peer)
            else:
                logger.error(f"[Transport] Key exchange failed with {hello.node_id}")
                writer.close()

        except Exception as e:
            logger.error(f"[Transport] Error handling client: {e}")
        finally:
            if not writer.is_closing():
                writer.close()

    async def _server_key_exchange(self, peer: PeerConnection) -> bool:
        """Perform server-side key exchange."""
        try:
            rs = self._get_rust_core()
            if not rs:
                return False

            # Wait for KEY_EXCHANGE from client
            msg = await self._read_message(peer.reader)
            if not msg or msg.header.msg_type != MessageType.KEY_EXCHANGE:
                return False

            ke_payload = KeyExchangePayload.unpack(msg.payload)
            peer.session_id = ke_payload.session_id

            # Decapsulate to get session key
            derived_key = rs.kem_decapsulate(
                self.decapsulation_key, ke_payload.ciphertext
            )
            peer.session_key = bytes.fromhex(derived_key)

            # Send KEY_EXCHANGE_ACK
            ack = self._message_builder.build(MessageType.KEY_EXCHANGE_ACK, b"OK")
            await self._send_message(peer.writer, ack)

            peer.state = ConnectionState.ESTABLISHED
            logger.info(f"[Transport] Key exchange complete with {peer.node_id}")
            return True

        except Exception as e:
            logger.error(f"[Transport] Key exchange error: {e}")
            return False

    # --- Client ---

    async def connect_to_peer(
        self, host: str, port: int = DEFAULT_TCP_PORT
    ) -> Optional[PeerConnection]:
        """Connect to a remote federation node."""
        peer_key = f"{host}:{port}"
        if peer_key in self.pending_connections:
            logger.warning(f"[Transport] Connection already pending to {peer_key}")
            return None

        self.pending_connections.add(peer_key)

        try:
            ssl_context = None
            if self.config.enable_tls:
                ssl_context = ssl.create_default_context()

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=ssl_context),
                timeout=self.config.connection_timeout,
            )

            # Send HELLO (use public keys for sharing)
            hello = self._message_builder.build_hello(
                self.encapsulation_key, self.signing_public_key
            )
            await self._send_message(writer, hello)

            # Wait for HELLO_ACK
            ack = await self._read_message(reader)
            if not ack or ack.header.msg_type != MessageType.HELLO_ACK:
                logger.error(f"[Transport] Expected HELLO_ACK from {host}")
                writer.close()
                return None

            # Parse remote keys
            remote_hello = HelloPayload.unpack(ack.payload)

            peer = PeerConnection(
                node_id=remote_hello.node_id,
                host=host,
                port=port,
                state=ConnectionState.KEY_EXCHANGE,
                reader=reader,
                writer=writer,
                encapsulation_key=remote_hello.encapsulation_key,
                signing_key=remote_hello.signing_key,
            )

            # Perform key exchange
            if await self._client_key_exchange(peer):
                peer.state = ConnectionState.ESTABLISHED
                self.peers[peer.node_id] = peer

                if self._on_peer_connected:
                    await self._on_peer_connected(peer)

                # Start message loop in background
                asyncio.create_task(self._message_loop(peer))

                logger.info(f"[Transport] Connected to {peer.node_id} at {host}:{port}")
                return peer
            else:
                writer.close()
                return None

        except asyncio.TimeoutError:
            logger.error(f"[Transport] Connection timeout to {host}:{port}")
            return None
        except Exception as e:
            logger.error(f"[Transport] Connection error to {host}:{port}: {e}")
            return None
        finally:
            self.pending_connections.discard(peer_key)

    async def _client_key_exchange(self, peer: PeerConnection) -> bool:
        """Perform client-side key exchange."""
        try:
            rs = self._get_rust_core()
            if not rs:
                return False

            # Encapsulate to remote's key
            derived_key, ciphertext = rs.kem_encapsulate(peer.encapsulation_key)

            # Generate session ID
            import os

            session_id = os.urandom(16)
            peer.session_id = session_id
            peer.session_key = bytes.fromhex(derived_key)

            # Send KEY_EXCHANGE
            ke_msg = self._message_builder.build_key_exchange(ciphertext, session_id)
            await self._send_message(peer.writer, ke_msg)

            # Wait for ACK
            ack = await self._read_message(peer.reader)
            if not ack or ack.header.msg_type != MessageType.KEY_EXCHANGE_ACK:
                return False

            logger.info(f"[Transport] Key exchange complete with {peer.node_id}")
            return True

        except Exception as e:
            logger.error(f"[Transport] Key exchange error: {e}")
            return False

    async def disconnect_peer(self, node_id: str) -> None:
        """Disconnect from a peer."""
        peer = self.peers.pop(node_id, None)
        if peer:
            peer.state = ConnectionState.CLOSING
            if peer.writer and not peer.writer.is_closing():
                peer.writer.close()

            if self._on_peer_disconnected:
                await self._on_peer_disconnected(peer)

            logger.info(f"[Transport] Disconnected from {node_id}")

    # --- Message Handling ---

    async def _message_loop(self, peer: PeerConnection) -> None:
        """Main message processing loop for a peer."""
        try:
            while self._running and peer.state == ConnectionState.ESTABLISHED:
                msg = await self._read_message(peer.reader)
                if not msg:
                    break

                peer.last_seen = time.time()
                peer.messages_received += 1

                # Handle message
                await self._dispatch_message(peer, msg)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[Transport] Message loop error for {peer.node_id}: {e}")
        finally:
            if peer.node_id in self.peers:
                await self.disconnect_peer(peer.node_id)

    async def _dispatch_message(
        self, peer: PeerConnection, msg: FederationMessage
    ) -> None:
        """Dispatch message to appropriate handler."""
        msg_type = msg.header.msg_type

        # Built-in handlers
        if msg_type == MessageType.PING:
            pong = self._message_builder.build_pong(msg.header.timestamp)
            await self._send_message(peer.writer, pong)
            return

        if msg_type == MessageType.PONG:
            # Calculate latency
            now = int(time.time() * 1_000_000)
            latency_us = now - msg.header.timestamp
            peer.latency_ms = latency_us / 1000.0
            return

        # Custom handlers
        handler = self._message_handlers.get(msg_type)
        if handler:
            try:
                await handler(peer, msg)
            except Exception as e:
                logger.error(f"[Transport] Handler error for {msg_type}: {e}")
        else:
            logger.warning(f"[Transport] No handler for message type {msg_type}")

    def register_handler(
        self, msg_type: MessageType, handler: Callable[..., Any]
    ) -> None:
        """Register a message handler."""
        self._message_handlers[msg_type] = handler

    def on_peer_connected(self, callback: Callable[..., Any]) -> None:
        """Set callback for peer connection."""
        self._on_peer_connected = callback

    def on_peer_disconnected(self, callback: Callable[..., Any]) -> None:
        """Set callback for peer disconnection."""
        self._on_peer_disconnected = callback

    # --- I/O ---

    async def _send_message(
        self, writer: Optional[asyncio.StreamWriter], msg: FederationMessage
    ) -> bool:
        """Send a message to a peer."""
        if writer is None:
            return False
        try:
            data = msg.pack()
            writer.write(data)
            await writer.drain()
            return True
        except Exception as e:
            logger.error(f"[Transport] Send error: {e}")
            return False

    async def _read_message(
        self, reader: Optional[asyncio.StreamReader]
    ) -> Optional[FederationMessage]:
        """Read a message from a peer."""
        if reader is None:
            return None
        try:
            # Read header
            header_data = await asyncio.wait_for(
                reader.readexactly(ProtocolHeader.HEADER_SIZE),
                timeout=self.config.connection_timeout,
            )
            header = ProtocolHeader.unpack(header_data)

            # Read rest of message
            remaining = (
                FederationMessage.SENDER_ID_SIZE
                + header.payload_len
                + FederationMessage.SIGNATURE_SIZE
            )

            if remaining > self.config.max_message_size:
                logger.error(f"[Transport] Message too large: {remaining}")
                return None

            rest_data = await asyncio.wait_for(
                reader.readexactly(remaining),
                timeout=self.config.connection_timeout,
            )

            return FederationMessage.unpack(header_data + rest_data)

        except asyncio.TimeoutError:
            logger.warning("[Transport] Read timeout")
            return None
        except asyncio.IncompleteReadError:
            return None
        except Exception as e:
            logger.error(f"[Transport] Read error: {e}")
            return None

    # --- Utility ---

    async def send_to_peer(
        self, node_id: str, msg_type: MessageType, payload: bytes
    ) -> bool:
        """Send a message to a specific peer."""
        peer = self.peers.get(node_id)
        if not peer or peer.state != ConnectionState.ESTABLISHED:
            return False

        msg = self._message_builder.build(msg_type, payload)
        result = await self._send_message(peer.writer, msg)
        if result:
            peer.messages_sent += 1
        return result

    async def broadcast(self, msg_type: MessageType, payload: bytes) -> int:
        """Broadcast a message to all connected peers."""
        count = 0
        for node_id in list(self.peers.keys()):
            if await self.send_to_peer(node_id, msg_type, payload):
                count += 1
        return count

    async def ping_peer(self, node_id: str) -> Optional[float]:
        """Ping a peer and return latency in ms."""
        peer = self.peers.get(node_id)
        if not peer:
            return None

        ping = self._message_builder.build_ping()
        await self._send_message(peer.writer, ping)

        # Wait for pong (handled in dispatch)
        await asyncio.sleep(0.1)
        return peer.latency_ms

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to all peers."""
        while self._running:
            await asyncio.sleep(self.config.heartbeat_interval)

            for peer in list(self.peers.values()):
                if peer.state == ConnectionState.ESTABLISHED:
                    ping = self._message_builder.build_ping()
                    await self._send_message(peer.writer, ping)

    def get_connected_peers(self) -> List[str]:
        """Get list of connected peer node IDs."""
        return [
            p.node_id
            for p in self.peers.values()
            if p.state == ConnectionState.ESTABLISHED
        ]

    def get_peer_stats(self, node_id: str) -> Optional[Dict]:
        """Get statistics for a peer."""
        peer = self.peers.get(node_id)
        if not peer:
            return None

        return {
            "node_id": peer.node_id,
            "host": peer.host,
            "port": peer.port,
            "state": peer.state.value,
            "latency_ms": peer.latency_ms,
            "messages_sent": peer.messages_sent,
            "messages_received": peer.messages_received,
            "last_seen": peer.last_seen,
        }
