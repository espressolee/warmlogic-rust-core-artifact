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
import json
import socket
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.mesh.beacon import Beacon


class TestBeaconCoverage(unittest.TestCase):
    def setUp(self):
        self.peer_manager = MagicMock()
        self.node_id = "node_123"
        self.http_port = 8080
        self.beacon_port = 9000
        self.beacon = Beacon(
            self.node_id, self.http_port, self.peer_manager, self.beacon_port
        )

    def tearDown(self):
        self.beacon.stop()

    def test_init(self):
        self.assertEqual(self.beacon.node_id, self.node_id)
        self.assertEqual(self.beacon.beacon_port, self.beacon_port)
        self.peer_manager.set_local_id.assert_called_with(self.node_id)

    @patch("threading.Thread")
    def test_start_stop(self, mock_thread):
        self.assertFalse(self.beacon._running)
        self.beacon.start()
        self.assertTrue(self.beacon._running)
        self.assertEqual(mock_thread.call_count, 2)  # Broadcast + Listen

        # Start again should be no-op
        self.beacon.start()
        self.assertEqual(mock_thread.call_count, 2)

        self.beacon.stop()
        self.assertFalse(self.beacon._running)

    @patch("socket.socket")
    @patch(
        "time.sleep", side_effect=[None, Exception("StopLoop")]
    )  # Run once then error to stop
    def test_broadcast_loop(self, mock_sleep, mock_socket):
        sock_instance = MagicMock()
        mock_socket.return_value = sock_instance

        # We need to stop the loop manually or via side effect
        # Here we use side_effect on sleep to break the loop or mock _running
        self.beacon._running = True

        # Inject an exception to break the loop after one iteraion if needed
        # But beacon code catches exceptions.
        # We can mock _running to become False after first iteration?
        # A clearer way: mock time.sleep to set _running = False
        def stop_running(*args):
            self.beacon._running = False

        mock_sleep.side_effect = stop_running

        self.beacon._broadcast_loop()

        # Check socket config
        sock_instance.setsockopt.assert_any_call(
            socket.SOL_SOCKET, socket.SO_BROADCAST, 1
        )

        # Check sendto
        expected_payload = json.dumps(
            {"type": "beacon", "node_id": self.node_id, "http_port": self.http_port}
        ).encode("utf-8")
        sock_instance.sendto.assert_called_with(
            expected_payload, ("<broadcast>", self.beacon_port)
        )
        sock_instance.close.assert_called_once()

    @patch("socket.socket")
    def test_broadcast_loop_error(self, mock_socket):
        sock_instance = MagicMock()
        mock_socket.return_value = sock_instance
        sock_instance.sendto.side_effect = Exception("Send Error")

        # Run one iteration
        with patch("time.sleep") as mock_sleep:
            mock_sleep.side_effect = lambda x: setattr(self.beacon, "_running", False)
            self.beacon._running = True

            # Should catch exception and not crash
            self.beacon._broadcast_loop()

        sock_instance.close.assert_called()

    @patch("socket.socket")
    @patch("warm_logic.mesh.beacon.ChaosMonkey")
    def test_listen_loop(self, MockChaosMonkey, mock_socket):
        # Disable chaos for basic test
        cm = MockChaosMonkey.return_value
        cm.enabled = False

        sock_instance = MagicMock()
        mock_socket.return_value = sock_instance

        # Prepare a valid packet
        payload = json.dumps(
            {"type": "beacon", "node_id": "remote_node", "http_port": 9090}
        ).encode("utf-8")
        sock_instance.recvfrom.return_value = (payload, ("192.168.1.5", 55555))

        # Run one iteration
        with patch("threading.Thread"):  # prevent actual threads if any
            self.beacon._running = True
            # We need to break the loop.
            # The loop calls handle_packet.
            # We can patch handle_packet or just let it run one successful recv then stop

            # Mock recvfrom to return data once, then raise exception to stop or check running?
            # Better: Mock handle_packet to set running=False
            original_handle = self.beacon._handle_packet

            def handle_and_stop(data, addr):
                original_handle(data, addr)
                self.beacon._running = False

            self.beacon._handle_packet = handle_and_stop

            self.beacon._listen_loop()

            self.peer_manager.register_peer.assert_called_with(
                "remote_node", "192.168.1.5", 9090
            )

    def test_handle_packet_chaos_drop(self):
        from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey

        ChaosMonkey.configure(enabled=True, drop_rate=1.0)

        data = b'{"type": "beacon", "node_id": "remote", "http_port": 80}'
        addr = ("127.0.0.1", 1234)

        # We must mock sleep to avoid actual delay if any
        with patch("time.sleep"):
            self.beacon._handle_packet(data, addr)

        self.peer_manager.register_peer.assert_not_called()
        ChaosMonkey.reset()

    def test_handle_packet_chaos_latency(self):
        from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey
        from warm_logic.mesh.topology import NetworkTopology

        ChaosMonkey.configure(enabled=True, latency_ms=100)

        # Inject region for the remote addr
        NetworkTopology.register_node(b"remote", NetworkTopology.US_EAST)

        data = json.dumps(
            {"type": "beacon", "node_id": "remote", "http_port": 80}
        ).encode("utf-8")

        with patch("time.sleep") as mock_sleep:
            self.beacon._handle_packet(data, ("1.1.1.1", 1234))
            self.assertTrue(mock_sleep.called)

        self.peer_manager.register_peer.assert_called()
        ChaosMonkey.reset()

    def test_handle_packet_corruption(self):
        from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey

        ChaosMonkey.configure(enabled=True, corruption_rate=1.0)

        payload = json.dumps(
            {"type": "beacon", "node_id": "remote", "http_port": 80}
        ).encode("utf-8")

        self.beacon._handle_packet(payload, ("1.1.1.1", 1234))

        # Corruption makes JSON decode fail or node_id mismatch
        self.peer_manager.register_peer.assert_not_called()
        ChaosMonkey.reset()

    def test_handle_packet_malformed(self):
        # Disable CM
        with patch("warm_logic.mesh.beacon.ChaosMonkey") as MockCM:
            MockCM.return_value.enabled = False

            # Non-JSON
            self.beacon._handle_packet(b"junk", ("1.1.1.1", 1234))
            self.peer_manager.register_peer.assert_not_called()

            # Missing fields
            self.beacon._handle_packet(b'{"type": "beacon"}', ("1.1.1.1", 1234))
            self.peer_manager.register_peer.assert_not_called()

            # Wrong type
            self.beacon._handle_packet(
                b'{"type": "other", "node_id": "x", "http_port": 1}', ("1.1.1.1", 1234)
            )
            self.peer_manager.register_peer.assert_not_called()

    @patch("socket.socket")
    def test_listen_bind_fail(self, mock_socket):
        sock = MagicMock()
        mock_socket.return_value = sock
        sock.bind.side_effect = OSError("Bind fail")

        with patch("builtins.print") as mock_print:
            self.beacon._listen_loop()
            # print should be called with error
            self.assertTrue(
                any("Failed to bind" in str(c) for c in mock_print.call_args_list)
            )


if __name__ == "__main__":
    unittest.main()
