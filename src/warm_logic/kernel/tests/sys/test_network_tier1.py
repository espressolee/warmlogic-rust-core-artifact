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
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.network import MeshNetworking


@pytest.fixture
def mock_dht_cls():
    with patch("warm_logic.kernel.sys.network.SovereignDHT") as mock:
        yield mock


@pytest.fixture
def mock_mldsa_cls():
    with patch("warm_logic.kernel.sys.network.MLDSA") as mock:
        mock.return_value.generate_keypair.return_value.public_key = "test_pub_key"
        yield mock


def test_mesh_init_provided_id(mock_dht_cls):
    """Test init with explicit node_id."""
    node_id = b"my_id"
    mn = MeshNetworking(node_id=node_id)
    mock_dht_cls.assert_called_with(node_id, "127.0.0.1", 4000)
    assert mn.dht == mock_dht_cls.return_value


def test_mesh_init_generated_id(mock_dht_cls, mock_mldsa_cls):
    """Test init generating node_id via MLDSA."""
    mn = MeshNetworking(node_id=None)
    mock_mldsa_cls.assert_called()
    mock_dht_cls.assert_called()
    # verify node_id is hash of public key
    # since we mocked mldsa public key as "test_pub_key"
    # we don't need to verify exact hash, just that logic flowed.


@pytest.mark.asyncio
async def test_ignite(mock_dht_cls):
    """Test async ignite."""
    mn = MeshNetworking(node_id=b"id")
    # Setup async mocks
    mn.dht.start = MagicMock(return_value=asyncio.Future())
    mn.dht.start.return_value.set_result(None)
    mn.dht.bootstrap = MagicMock(return_value=asyncio.Future())
    mn.dht.bootstrap.return_value.set_result(None)

    await mn.ignite([("seed", 123)])

    # Verify await calls were made?
    # Since we mocked them as returning futures and awaited them, simple check:
    assert mn.dht.start.called or asyncio.iscoroutinefunction(mn.dht.start)
    # The current code uses typical async def methods or returns Awaitables.
    # MagicMock isn't async by default unless configured.
    # But code is: await self.dht.start()
    # So start() must return an awaitable.


def test_broadcast(mock_dht_cls):
    """Test broadcast logic."""
    mn = MeshNetworking(node_id=b"id")
    mn.dht.routing.find_neighbors.return_value = ["peer1", "peer2"]
    mn.dht.node_id = b"id"

    count = mn.broadcast(b"data")
    assert count == 2
    assert mn.dht.send.call_count == 2
    mn.dht.send.assert_any_call("peer1", b"data")


def test_get_mesh_status_empty(mock_dht_cls):
    """Test status with no neighbors."""
    mn = MeshNetworking(node_id=b"id")
    mn.dht.node_id = b"id"
    mn.dht.routing.find_neighbors.return_value = []

    status = mn.get_mesh_status()
    assert status["peer_count"] == 0
    assert status["is_sovereign"] is False
    assert status["pqc_bound"] is False


def test_get_mesh_status_pqc_valid(mock_dht_cls):
    """Test status with valid PQC neighbors."""
    mn = MeshNetworking(node_id=b"id")
    mn.dht.node_id = b"id"

    p1 = MagicMock()
    p1.public_key = "key1"
    mn.dht.routing.find_neighbors.return_value = [p1]

    status = mn.get_mesh_status()
    assert status["peer_count"] == 1
    assert status["is_sovereign"] is True
    assert status["pqc_bound"] is True


def test_get_mesh_status_pqc_invalid(mock_dht_cls):
    """Test status with some invalid PQC neighbors."""
    mn = MeshNetworking(node_id=b"id")
    mn.dht.node_id = b"id"

    p1 = MagicMock()
    p1.public_key = "key1"
    p2 = MagicMock()
    p2.public_key = None  # Invalid
    mn.dht.routing.find_neighbors.return_value = [p1, p2]

    status = mn.get_mesh_status()
    assert status["peer_count"] == 2
    assert status["is_sovereign"] is True
    assert status["pqc_bound"] is False  # All must be valid
