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
import hashlib
from unittest import mock

from warm_logic.kernel.sys.cryptography import PQCKeypair
from warm_logic.kernel.sys.network import MeshNetworking
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestNetworkCoverage(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        self.mldsa_patcher = mock.patch("warm_logic.kernel.sys.network.MLDSA")
        self.mock_mldsa_cls = self.mldsa_patcher.start()
        # Mock MLDSA instance to avoid RuntimeError and provide keypair
        self.mock_mldsa = self.mock_mldsa_cls.return_value
        self.mock_keys = PQCKeypair(public_key="test_key", private_key="test_priv")
        self.mock_mldsa.generate_keypair.return_value = self.mock_keys

    def tearDown(self):
        self.mldsa_patcher.stop()
        super().tearDown()

    def test_init_auto_id(self):
        mn = MeshNetworking()
        expected = hashlib.sha3_256("test_key".encode()).digest()
        self.assertEqual(mn.dht.node_id, expected)
    def test_init_explicit(self):
        nid = b"\x00" * 32
        mn = MeshNetworking(node_id=nid)
        self.assertEqual(mn.dht.node_id, nid)

    async def test_ignite(self):
        mn = MeshNetworking()
        mn.dht.start = mock.AsyncMock()
        mn.dht.bootstrap = mock.AsyncMock()

        await mn.ignite([("seed", 80)])
        mn.dht.start.assert_called_once()
        mn.dht.bootstrap.assert_called_once_with([("seed", 80)])


    def test_broadcast(self):
        mn = MeshNetworking()
        with mock.patch.object(mn.dht.routing, "find_neighbors") as mock_find:
            mock_peer = mock.MagicMock()
            mock_find.return_value = [mock_peer]
            # Mock dht.send since it's the new method we added
            mn.dht.send = mock.Mock()
            count = mn.broadcast(b"test")
            self.assertEqual(count, 1)
            mn.dht.send.assert_called_once()

    def test_mesh_status(self):
        mn = MeshNetworking()
        # Mock neighbor needed for is_sovereign=True
        mock_peer = mock.Mock()
        mock_peer.public_key = "key"
        with mock.patch.object(mn.dht.routing, "find_neighbors", return_value=[mock_peer]):
            status = mn.get_mesh_status()
            self.assertEqual(status["is_sovereign"], True)
