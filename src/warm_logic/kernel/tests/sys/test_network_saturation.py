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
import unittest
from unittest import mock
from warm_logic.kernel.sys.network import MeshNetworking
from warm_logic.kernel.sys.cryptography import PQCKeypair

class TestNetworkSaturation(unittest.TestCase):
    def setUp(self):
        # Patch MLDSA to avoid Rust init errors during KeyGen in MeshNetworking init
        self.mldsa_patcher = mock.patch("warm_logic.kernel.sys.network.MLDSA")
        self.mock_mldsa_cls = self.mldsa_patcher.start()
        self.mock_mldsa = self.mock_mldsa_cls.return_value
        self.mock_keys = PQCKeypair(public_key="test_key", private_key="test_priv")
        self.mock_mldsa.generate_keypair.return_value = self.mock_keys

    def tearDown(self):
        self.mldsa_patcher.stop()

    def test_broadcast_isolated(self):
        """Test broadcast with ZERO neighbors."""
        mn = MeshNetworking()
        # Mock finding neighbors to return empty list
        with mock.patch.object(mn.dht.routing, "find_neighbors", return_value=[]):
            count = mn.broadcast(b"payload")
            self.assertEqual(count, 0)

    def test_mesh_status_isolated(self):
        """Test status when node is isolated (is_sovereign=False)."""
        mn = MeshNetworking()
        with mock.patch.object(mn.dht.routing, "find_neighbors", return_value=[]):
            status = mn.get_mesh_status()
            self.assertFalse(status["is_sovereign"])
            self.assertFalse(status["pqc_bound"])
            self.assertEqual(status["peer_count"], 0)

    def test_mesh_status_legacy_peer(self):
        """Test status with a neighbor lacking PQC key (pqc_bound=False)."""
        mn = MeshNetworking()
        # Mock a legacy neighbor (simulate object with public_key=None)
        legacy_peer = mock.Mock()
        legacy_peer.public_key = None

        with mock.patch.object(mn.dht.routing, "find_neighbors", return_value=[legacy_peer]):
            status = mn.get_mesh_status()
            self.assertTrue(status["is_sovereign"])
            # Should be False because ONE neighbor lacks key
            self.assertFalse(status["pqc_bound"])
            self.assertEqual(status["peer_count"], 1)

if __name__ == "__main__":
    unittest.main()
