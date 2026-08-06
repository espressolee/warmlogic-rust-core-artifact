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
Network Transport Tests

Tests for the async network transport layer.
"""

import asyncio
import hashlib
import socket
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel import rust_loader
from warm_logic.kernel.federation.network_transport import (
    ConnectionState,
    FederationTransport,
    PeerConnection,
    TransportConfig,
)
from warm_logic.kernel.federation.protocol import MessageType


def _can_bind_tcp_socket() -> bool:
    """Return True when the current environment permits local TCP bind."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 0))
        return True
    except OSError:
        return False
    finally:
        sock.close()


_TCP_BIND_AVAILABLE = _can_bind_tcp_socket()


class _DeterministicRustShim:
    """Minimal deterministic shim for transport tests when Rust extension is absent."""

    def kem_keygen(self):
        seed = hashlib.sha256(b"kem_keygen").hexdigest()
        return seed, hashlib.sha256(f"dk:{seed}".encode()).hexdigest()

    def generate_keypair(self):
        seed = hashlib.sha256(b"sign_keygen").hexdigest()
        return seed, hashlib.sha256(f"sk:{seed}".encode()).hexdigest()

    def kem_encapsulate(self, encapsulation_key: str):
        ciphertext = hashlib.sha256(f"ct:{encapsulation_key}".encode()).hexdigest()
        shared = hashlib.sha256(f"shared:{ciphertext}".encode()).hexdigest()
        return shared, ciphertext

    def kem_decapsulate(self, decapsulation_key: str, ciphertext: str):
        _ = decapsulation_key  # Interface parity with real Rust core
        return hashlib.sha256(f"shared:{ciphertext}".encode()).hexdigest()

    def sign(self, signing_key: str, message_hash: str):
        digest = hashlib.sha256(f"{signing_key}:{message_hash}".encode()).hexdigest()
        # Protocol truncates to 64 bytes; provide stable 64-byte signature hex.
        return digest * 2


def _bootstrap_rust_core():
    """Return (core, patcher). patcher is active only when shimmed."""
    if rust_loader.HAS_RUST_CORE:
        return rust_loader.load_rust_core(), None

    shim = _DeterministicRustShim()
    patcher = patch.multiple(
        rust_loader,
        HAS_RUST_CORE=True,
        load_rust_core=MagicMock(return_value=shim),
    )
    patcher.start()
    return shim, patcher


class TestTransportConfig(unittest.TestCase):
    """Test TransportConfig dataclass."""

    def test_default_config(self):
        config = TransportConfig()
        self.assertEqual(config.tcp_port, 17300)
        self.assertEqual(config.udp_port, 17301)
        self.assertEqual(config.max_connections, 64)
        self.assertEqual(config.heartbeat_interval, 30.0)

    def test_custom_config(self):
        config = TransportConfig(
            tcp_port=18000,
            max_connections=128,
            enable_tls=True,
        )
        self.assertEqual(config.tcp_port, 18000)
        self.assertEqual(config.max_connections, 128)
        self.assertTrue(config.enable_tls)


class TestPeerConnection(unittest.TestCase):
    """Test PeerConnection dataclass."""

    def test_peer_creation(self):
        peer = PeerConnection(
            node_id="wl-test-peer",
            host="192.168.1.100",
            port=17300,
        )
        self.assertEqual(peer.node_id, "wl-test-peer")
        self.assertEqual(peer.state, ConnectionState.DISCONNECTED)
        self.assertGreater(peer.last_seen, 0)

    def test_peer_state_transitions(self):
        peer = PeerConnection(
            node_id="wl-test",
            host="localhost",
            port=17300,
        )
        peer.state = ConnectionState.CONNECTING
        self.assertEqual(peer.state, ConnectionState.CONNECTING)

        peer.state = ConnectionState.ESTABLISHED
        self.assertEqual(peer.state, ConnectionState.ESTABLISHED)


class TestConnectionState(unittest.TestCase):
    """Test ConnectionState enum."""

    def test_state_values(self):
        self.assertEqual(ConnectionState.DISCONNECTED.value, "disconnected")
        self.assertEqual(ConnectionState.CONNECTING.value, "connecting")
        self.assertEqual(ConnectionState.HANDSHAKING.value, "handshaking")
        self.assertEqual(ConnectionState.KEY_EXCHANGE.value, "key_exchange")
        self.assertEqual(ConnectionState.ESTABLISHED.value, "established")
        self.assertEqual(ConnectionState.CLOSING.value, "closing")


class TestFederationTransport(unittest.TestCase):
    """Test FederationTransport class."""

    @classmethod
    def setUpClass(cls):
        """Set up test keys."""
        rs, cls._rust_patcher = _bootstrap_rust_core()
        cls.ek1, cls.dk1 = rs.kem_keygen()
        cls.pk1, cls.sk1 = rs.generate_keypair()
        cls.ek2, cls.dk2 = rs.kem_keygen()
        cls.pk2, cls.sk2 = rs.generate_keypair()

    @classmethod
    def tearDownClass(cls):
        patcher = getattr(cls, "_rust_patcher", None)
        if patcher is not None:
            patcher.stop()

    def test_transport_creation(self):
        transport = FederationTransport(
            node_id="test-node-001",
            signing_key=self.sk1,
            encapsulation_key=self.ek1,
            decapsulation_key=self.dk1,
            signing_public_key=self.pk1,
        )
        self.assertEqual(transport.node_id, "test-node-001")
        self.assertEqual(len(transport.peers), 0)

    def test_transport_with_config(self):
        config = TransportConfig(tcp_port=18000)
        transport = FederationTransport(
            node_id="test-node-002",
            signing_key=self.sk1,
            encapsulation_key=self.ek1,
            decapsulation_key=self.dk1,
            signing_public_key=self.pk1,
            config=config,
        )
        self.assertEqual(transport.config.tcp_port, 18000)

    def test_register_handler(self):
        transport = FederationTransport(
            node_id="test-node-003",
            signing_key=self.sk1,
            encapsulation_key=self.ek1,
            decapsulation_key=self.dk1,
            signing_public_key=self.pk1,
        )

        async def dummy_handler(peer, msg):
            pass

        transport.register_handler(MessageType.PROPOSAL, dummy_handler)
        self.assertIn(MessageType.PROPOSAL, transport._message_handlers)

    def test_get_connected_peers_empty(self):
        transport = FederationTransport(
            node_id="test-node-004",
            signing_key=self.sk1,
            encapsulation_key=self.ek1,
            decapsulation_key=self.dk1,
            signing_public_key=self.pk1,
        )
        peers = transport.get_connected_peers()
        self.assertEqual(peers, [])

    def test_get_peer_stats_nonexistent(self):
        transport = FederationTransport(
            node_id="test-node-005",
            signing_key=self.sk1,
            encapsulation_key=self.ek1,
            decapsulation_key=self.dk1,
            signing_public_key=self.pk1,
        )
        stats = transport.get_peer_stats("nonexistent")
        self.assertIsNone(stats)


class TestTransportServerClient(unittest.TestCase):
    """Integration tests for server-client communication."""

    @classmethod
    def setUpClass(cls):
        """Set up test keys."""
        if not _TCP_BIND_AVAILABLE:
            raise unittest.SkipTest("TCP bind permission required")
        rs, cls._rust_patcher = _bootstrap_rust_core()
        cls.ek1, cls.dk1 = rs.kem_keygen()
        cls.pk1, cls.sk1 = rs.generate_keypair()
        cls.ek2, cls.dk2 = rs.kem_keygen()
        cls.pk2, cls.sk2 = rs.generate_keypair()

    @classmethod
    def tearDownClass(cls):
        patcher = getattr(cls, "_rust_patcher", None)
        if patcher is not None:
            patcher.stop()

    def test_server_start_stop(self):
        """Test server lifecycle."""

        async def run_test():
            transport = FederationTransport(
                node_id="server-node",
                signing_key=self.sk1,
                encapsulation_key=self.ek1,
                decapsulation_key=self.dk1,
                signing_public_key=self.pk1,
                config=TransportConfig(tcp_port=17350),
            )

            # Start server
            result = await transport.start_server()
            self.assertTrue(result)
            self.assertTrue(transport._running)

            # Stop server
            await transport.stop_server()
            self.assertFalse(transport._running)

        asyncio.run(run_test())

    def test_client_connect_no_server(self):
        """Test client connection to non-existent server."""

        async def run_test():
            transport = FederationTransport(
                node_id="client-node",
                signing_key=self.sk1,
                encapsulation_key=self.ek1,
                decapsulation_key=self.dk1,
                signing_public_key=self.pk1,
                config=TransportConfig(connection_timeout=1.0),
            )

            # Try connecting to non-existent server
            peer = await transport.connect_to_peer("127.0.0.1", 17399)
            self.assertIsNone(peer)

        asyncio.run(run_test())

    def test_server_client_handshake(self):
        """Test complete handshake between server and client."""

        async def run_test():
            connected_peers = []

            # Server
            server = FederationTransport(
                node_id="server-001",
                signing_key=self.sk1,
                encapsulation_key=self.ek1,
                decapsulation_key=self.dk1,
                signing_public_key=self.pk1,
                config=TransportConfig(tcp_port=17360),
            )

            async def on_connected(peer):
                connected_peers.append(peer.node_id)

            server.on_peer_connected(on_connected)

            # Start server
            await server.start_server()

            # Client
            client = FederationTransport(
                node_id="client-001",
                signing_key=self.sk2,
                encapsulation_key=self.ek2,
                decapsulation_key=self.dk2,
                signing_public_key=self.pk2,
                config=TransportConfig(connection_timeout=5.0),
            )

            # Connect
            peer = await client.connect_to_peer("127.0.0.1", 17360)
            self.assertIsNotNone(peer)
            self.assertEqual(peer.node_id, "server-001")
            self.assertEqual(peer.state, ConnectionState.ESTABLISHED)

            # Verify server side
            await asyncio.sleep(0.5)  # Wait for server to process
            self.assertIn("client-001", connected_peers)

            # Cleanup
            await client.disconnect_peer("server-001")
            await server.stop_server()

        asyncio.run(run_test())

    def test_ping_pong(self):
        """Test ping-pong latency measurement."""

        async def run_test():
            # Server
            server = FederationTransport(
                node_id="ping-server",
                signing_key=self.sk1,
                encapsulation_key=self.ek1,
                decapsulation_key=self.dk1,
                signing_public_key=self.pk1,
                config=TransportConfig(tcp_port=17370),
            )
            await server.start_server()

            # Client
            client = FederationTransport(
                node_id="ping-client",
                signing_key=self.sk2,
                encapsulation_key=self.ek2,
                decapsulation_key=self.dk2,
                signing_public_key=self.pk2,
            )

            peer = await client.connect_to_peer("127.0.0.1", 17370)
            self.assertIsNotNone(peer)

            # Send ping
            latency = await client.ping_peer("ping-server")
            # Latency should be positive (local connection is fast)
            self.assertIsNotNone(latency)

            # Cleanup
            await client.disconnect_peer("ping-server")
            await server.stop_server()

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
