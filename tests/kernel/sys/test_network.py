# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic network module."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.kernel.sys.network import MeshNetworking


class TestMeshNetworking:
    """Test MeshNetworking class."""

    @patch("warm_logic.kernel.sys.network.SovereignDHT")
    @patch("warm_logic.kernel.sys.network.MLDSA")
    def test_init_with_generated_node_id(self, mock_mldsa_class, mock_dht_class):
        """Generates node ID from PQC key when not provided."""
        mock_mldsa = MagicMock()
        mock_keys = MagicMock()
        mock_keys.public_key = "test-public-key"
        mock_mldsa.generate_keypair.return_value = mock_keys
        mock_mldsa_class.return_value = mock_mldsa

        mesh = MeshNetworking(address="0.0.0.0", port=8468)

        mock_mldsa.generate_keypair.assert_called_once()
        expected_node_id = hashlib.sha3_256(b"test-public-key").digest()
        mock_dht_class.assert_called_once_with(expected_node_id, "0.0.0.0", 8468)

    @patch("warm_logic.kernel.sys.network.SovereignDHT")
    def test_init_with_provided_node_id(self, mock_dht_class):
        """Uses provided node ID directly."""
        node_id = b"custom-node-id-32bytes-here----"

        mesh = MeshNetworking(node_id=node_id, address="1.2.3.4", port=9000)

        mock_dht_class.assert_called_once_with(node_id, "1.2.3.4", 9000)

    @pytest.mark.asyncio
    @patch("warm_logic.kernel.sys.network.SovereignDHT")
    async def test_ignite(self, mock_dht_class):
        """Ignites mesh network with bootstrap seeds."""
        mock_dht = MagicMock()
        mock_dht.start = AsyncMock()
        mock_dht.bootstrap = AsyncMock()
        mock_dht_class.return_value = mock_dht

        mesh = MeshNetworking(node_id=b"x" * 32)
        seeds = [("seed1.example.com", 8468), ("seed2.example.com", 8468)]
        await mesh.ignite(seeds)

        mock_dht.start.assert_called_once()
        mock_dht.bootstrap.assert_called_once_with(seeds)

    @patch("warm_logic.kernel.sys.network.SovereignDHT")
    def test_broadcast_to_neighbors(self, mock_dht_class):
        """Broadcasts message to all neighbors."""
        mock_peer1 = MagicMock()
        mock_peer2 = MagicMock()
        mock_routing = MagicMock()
        mock_routing.find_neighbors.return_value = [mock_peer1, mock_peer2]

        mock_dht = MagicMock()
        mock_dht.routing = mock_routing
        mock_dht.node_id = b"x" * 32
        mock_dht_class.return_value = mock_dht

        mesh = MeshNetworking(node_id=b"x" * 32)
        count = mesh.broadcast(b"test message")

        assert count == 2
        assert mock_dht.send.call_count == 2

    @patch("warm_logic.kernel.sys.network.SovereignDHT")
    def test_broadcast_no_neighbors(self, mock_dht_class):
        """Broadcast returns 0 when no neighbors."""
        mock_routing = MagicMock()
        mock_routing.find_neighbors.return_value = []

        mock_dht = MagicMock()
        mock_dht.routing = mock_routing
        mock_dht.node_id = b"x" * 32
        mock_dht_class.return_value = mock_dht

        mesh = MeshNetworking(node_id=b"x" * 32)
        count = mesh.broadcast(b"test message")

        assert count == 0

    @patch("warm_logic.kernel.sys.network.SovereignDHT")
    def test_get_mesh_status_with_pqc_peers(self, mock_dht_class):
        """Returns mesh status with PQC-bound peers."""
        mock_peer1 = MagicMock()
        mock_peer1.public_key = "pk1"
        mock_peer2 = MagicMock()
        mock_peer2.public_key = "pk2"

        mock_routing = MagicMock()
        mock_routing.find_neighbors.return_value = [mock_peer1, mock_peer2]

        mock_dht = MagicMock()
        mock_dht.routing = mock_routing
        mock_dht.node_id = bytes.fromhex("abcd1234" * 8)
        mock_dht_class.return_value = mock_dht

        mesh = MeshNetworking(node_id=bytes.fromhex("abcd1234" * 8))
        status = mesh.get_mesh_status()

        assert status["node_id"] == "abcd1234" * 8
        assert status["peer_count"] == 2
        assert status["is_sovereign"] is True
        assert status["pqc_bound"] is True

    @patch("warm_logic.kernel.sys.network.SovereignDHT")
    def test_get_mesh_status_no_peers(self, mock_dht_class):
        """Returns mesh status with no peers."""
        mock_routing = MagicMock()
        mock_routing.find_neighbors.return_value = []

        mock_dht = MagicMock()
        mock_dht.routing = mock_routing
        mock_dht.node_id = b"x" * 32
        mock_dht_class.return_value = mock_dht

        mesh = MeshNetworking(node_id=b"x" * 32)
        status = mesh.get_mesh_status()

        assert status["peer_count"] == 0
        assert status["is_sovereign"] is False
        assert status["pqc_bound"] is False

    @patch("warm_logic.kernel.sys.network.SovereignDHT")
    def test_get_mesh_status_non_pqc_peer(self, mock_dht_class):
        """Returns pqc_bound False when peer lacks public key."""
        mock_peer = MagicMock()
        mock_peer.public_key = None

        mock_routing = MagicMock()
        mock_routing.find_neighbors.return_value = [mock_peer]

        mock_dht = MagicMock()
        mock_dht.routing = mock_routing
        mock_dht.node_id = b"x" * 32
        mock_dht_class.return_value = mock_dht

        mesh = MeshNetworking(node_id=b"x" * 32)
        status = mesh.get_mesh_status()

        assert status["peer_count"] == 1
        assert status["is_sovereign"] is True
        assert status["pqc_bound"] is False
