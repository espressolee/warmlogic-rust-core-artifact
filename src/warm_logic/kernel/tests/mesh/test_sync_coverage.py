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
from unittest.mock import MagicMock, patch

from warm_logic.mesh.sync import SocialSyncAgent


class TestSyncCoverage(unittest.TestCase):
    def setUp(self):
        self.peer_manager = MagicMock()
        self.social_store = MagicMock()
        self.agent = SocialSyncAgent(self.peer_manager, self.social_store)

    def tearDown(self):
        self.agent.stop()

    def test_init(self):
        self.assertEqual(self.agent.peer_manager, self.peer_manager)
        self.assertEqual(self.agent.social_store, self.social_store)
        self.assertFalse(self.agent._running)

    @patch("threading.Thread")
    def test_start_stop(self, mock_thread):
        self.agent.start()
        self.assertTrue(self.agent._running)
        self.assertEqual(mock_thread.call_count, 1)

        self.agent.start()  # Idempotent
        self.assertEqual(mock_thread.call_count, 1)

        self.agent.stop()
        self.assertFalse(self.agent._running)

    def test_get_stats(self):
        self.peer_manager.get_peer_count.return_value = 5
        self.agent._sync_count = 10
        self.agent._last_sync_peer = "abc"

        stats = self.agent.get_stats()
        self.assertEqual(stats["sync_count"], 10)
        self.assertEqual(stats["last_peer"], "abc")
        self.assertEqual(stats["active_peers"], 5)

    @patch("time.sleep")
    @patch("random.choice")
    def test_sync_loop_basic(self, mock_choice, mock_sleep):
        # Mock running state
        self.agent._running = True

        # Stop after 1 iteration
        mock_sleep.side_effect = lambda x: setattr(self.agent, "_running", False)

        # Peer setup
        peer = MagicMock()
        peer.node_id = "peer_id_long_string"
        peer.address = "127.0.0.1"
        peer.http_port = 8080

        self.peer_manager.get_active_peers.return_value = [peer]
        mock_choice.return_value = peer

        # Mock _sync_from_peer to avoid actual HTTP
        with patch.object(self.agent, "_sync_from_peer") as mock_sync_call:
            self.agent._sync_loop()

            mock_sync_call.assert_called_with("127.0.0.1", 8080)
            self.assertEqual(self.agent._sync_count, 1)
            self.assertEqual(self.agent._last_sync_peer, "peer_id_long_str")  # sliced

    @patch("time.sleep")
    def test_sync_loop_no_peers(self, mock_sleep):
        self.agent._running = True
        mock_sleep.side_effect = lambda x: setattr(self.agent, "_running", False)

        self.peer_manager.get_active_peers.return_value = []

        with patch.object(self.agent, "_sync_from_peer") as mock_sync_call:
            self.agent._sync_loop()
            mock_sync_call.assert_not_called()

    @patch("warm_logic.kernel.substrate.chaos_monkey.ChaosMonkey")
    @patch("requests.get")
    def test_sync_from_peer_success(self, mock_requests, MockCM):
        MockCM.return_value.enabled = False

        response = MagicMock()
        response.json.return_value = [
            {
                "sender_id": "s1",
                "content": "hello",
                "signature": "sig",
                "timestamp": 12345,
            }
        ]
        response.status_code = 200
        mock_requests.return_value = response

        # Mock SocialMessage reconstruction if needed, or rely on real one?
        # The code imports from warm_logic.social.protocol.SovereignMessage inside loop
        # We should patch it to avoid dependency on social module internals if possible
        # Or if available, let it run.
        # Let's mock it for isolation
        with patch("warm_logic.social.protocol.SovereignMessage") as MockMsg:
            mock_msg_instance = MockMsg.return_value
            self.social_store.add_message.return_value = True  # Added new

            self.agent._sync_from_peer("1.1.1.1", 80)

            MockMsg.assert_called()
            self.social_store.add_message.assert_called_with(mock_msg_instance)

    @patch("warm_logic.kernel.substrate.chaos_monkey.ChaosMonkey")
    def test_sync_from_peer_chaos_drop(self, MockCM):
        cm = MockCM.return_value
        cm.enabled = True
        cm.drop_rate = 1.0  # Drop

        with self.assertRaisesRegex(Exception, "ChaosMonkey: Network Drop"):
            self.agent._sync_from_peer("1.1.1.1", 80)

    @patch("warm_logic.kernel.substrate.chaos_monkey.ChaosMonkey")
    @patch("warm_logic.mesh.topology.NetworkTopology.get_latency")
    @patch("time.sleep")
    @patch("requests.get")
    def test_sync_from_peer_chaos_latency(
        self, mock_req, mock_sleep, mock_topo, MockCM
    ):
        cm = MockCM.return_value
        cm.enabled = True
        cm.drop_rate = 0.0
        cm.latency_ms = 100

        mock_topo.return_value = 0

        mock_req.return_value.status_code = 200
        mock_req.return_value.json.return_value = []

        self.agent._sync_from_peer("1.1.1.1", 80)

        self.assertTrue(mock_sleep.called)

    @patch("warm_logic.kernel.substrate.chaos_monkey.ChaosMonkey")
    @patch("requests.get")
    def test_sync_from_peer_malformed_response(self, mock_requests, MockCM):
        MockCM.return_value.enabled = False

        response = MagicMock()
        response.json.return_value = [{"bad": "data"}]
        mock_requests.return_value = response

        with patch("warm_logic.social.protocol.SovereignMessage") as MockMsg:
            MockMsg.side_effect = Exception("Validation Error")

            self.agent._sync_from_peer("1.1.1.1", 80)

            # verify we didn't add anything
            self.social_store.add_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
