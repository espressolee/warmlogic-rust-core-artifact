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
import json
import time
import unittest
from unittest.mock import MagicMock, mock_open, patch

from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey
from warm_logic.kernel.substrate.cluster import (
    ClusterConfig,
    ClusterNode,
    ClusterOrchestrator,
    NodeState,
)
from warm_logic.kernel.substrate.network_bridge import (
    BlockPropagationHandler,
    NetworkBridge,
    NetworkMessage,
)
from warm_logic.kernel.substrate.stitch_server import StitchServer


class TestWave14Saturation(unittest.IsolatedAsyncioTestCase):
    """
    Substrate & Infrastructure Saturation Suite.
    Eliminating coverage gaps in Cluster, NetworkBridge, StitchServer, and ChaosMonkey.
    """

    def setUp(self):
        StitchServer.reset()
        ChaosMonkey.reset()
        import warm_logic.kernel.substrate.stitch_server as ss

        ss._subscribers.clear()
        ss._handlers.clear()
        ss._event_buffer.clear()

    async def test_cluster_perfection(self):
        """Cover cluster.py: lifecycle, handlers, monitor, and edge cases."""
        node_id = "node_1"
        config = ClusterConfig("cluster_1", heartbeat_interval=0.1, node_timeout=0.2)
        orch = ClusterOrchestrator(node_id, config)
        bridge = NetworkBridge(node_id)
        orch.connect_network(bridge)
        orch.connect_stitch(MagicMock())

        # 1. Lifecycle & Health
        peer = ClusterNode("peer_1", "1.1.1.1", 80)
        orch.add_node(peer)
        self.assertIn("peer_1", orch._nodes)
        self.assertGreaterEqual(orch.config.quorum_size, 2)
        self.assertGreaterEqual(len(orch.get_nodes()), 2)

        # Trigger join_cluster with exception
        with patch.object(bridge, "send_to_peer", side_effect=Exception("fail")):
            self.assertFalse(orch.join_cluster("2.2.2.2", 80))

        # Trigger empty seed join
        self.assertFalse(orch.join_cluster("", 0))

        # 2. Handlers & Term Logic
        with self.assertLogs("ClusterOrchestrator", level="WARNING"):
            orch._handle_join_request({"cluster_id": "WRONG"})

        orch._handle_heartbeat(
            {"node_id": "peer_1", "term": 100, "leader_id": "peer_1"}
        )
        self.assertEqual(orch._term, 100)
        self.assertEqual(orch._current_leader, "peer_1")

        orch._handle_vote_request({"candidate_id": "peer_1", "term": 200})
        self.assertEqual(orch._term, 200)

        # 3. Monitor Loop & Partition (Adjust timing)
        orch.config.node_timeout = 0.4
        orch.config.heartbeat_interval = 0.05
        peer.last_heartbeat = time.time() - 0.15  # Degraded (>0.1)

        async def wait_for_peer_state(expected_states, timeout: float = 1.0):
            deadline = time.time() + timeout
            while time.time() < deadline:
                if peer.state in expected_states:
                    return
                await asyncio.sleep(0.02)
            self.fail(
                f"peer.state={peer.state} did not reach {tuple(expected_states)} "
                f"within {timeout}s"
            )

        await orch.start()
        await wait_for_peer_state({NodeState.DEGRADED, NodeState.UNREACHABLE})
        self.assertIn(peer.state, (NodeState.DEGRADED, NodeState.UNREACHABLE))

        partition_cb = MagicMock()
        orch._on_partition = partition_cb
        peer.state = NodeState.HEALTHY
        peer.last_heartbeat = time.time() - 0.6  # Unreachable (>0.4)
        await wait_for_peer_state({NodeState.UNREACHABLE})
        self.assertEqual(peer.state, NodeState.UNREACHABLE)
        partition_cb.assert_called()

        # 4. Status & Stop
        self.assertIsNotNone(orch.get_status())
        await orch.stop()

    def test_network_bridge_perfection(self):
        """Cover network_bridge.py: Rust errors, broadcasting, and routing."""
        bridge = NetworkBridge("node_b")
        bridge.connect_stitch(MagicMock())
        bridge.connect_bft(MagicMock())

        # 1. Rust DHT Error Paths (ImportError)

        with patch.dict("sys.modules", {"warm_logic_rs": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                self.assertFalse(bridge.connect_rust_dht())
                # Hit vote handler ImportError
                bridge._handle_vote(
                    NetworkMessage("VOTE", "s1", {"block_hash": "h1"}, time.time())
                )

        # 2. Rust DHT Execution Errors
        bridge._rust_dht = MagicMock()
        bridge._rust_dht.update.side_effect = Exception("fail")
        bridge.add_peer("p1", "1.1.1.1", 80)

        bridge._rust_dht.send.side_effect = Exception("fail")
        bridge.broadcast("B", {})
        bridge.send_to_peer("p1", "S", {})

        # 3. SSE Broadcast failure
        with patch(
            "warm_logic.kernel.substrate.stitch_server.StitchServer.broadcast",
            side_effect=Exception,
        ):
            bridge._broadcast_sse("E", {})

        # 4. Routing & Handlers
        router = bridge.router
        router.register_handler("X", MagicMock(side_effect=Exception))
        router.route(json.dumps({"type": "X", "sender_id": "s"}).encode(), "1.1.1.1")
        router.route(b"not json", "1.1.1.1")
        self.assertGreaterEqual(router.get_stats()["handler_errors"], 1)

    def test_stitch_server_perfection(self):
        """Cover stitch_server.py: SSE, POST, and Re-sync."""
        server = StitchServer("127.0.0.1", 0)
        server.start()

        for _ in range(10):
            if server.port != 0:
                break
            time.sleep(0.1)

        port = server.port
        if port == 0:
            # Sandbox fallback: keep protocol/buffer coverage without loopback socket.
            from warm_logic.kernel.substrate.stitch_server import (
                StitchRequestHandler,
                _buffer_lock,
                _event_buffer,
            )

            with _buffer_lock:
                _event_buffer.append((1, "test", {"data": 1}))

            mock_handler = MagicMock()
            mock_handler.path = "/stream"
            mock_handler.headers = {"Last-Event-ID": "0"}
            mock_handler.server = MagicMock()
            mock_handler.client_address = ("127.0.0.1", 12345)
            with patch("queue.Queue.get", side_effect=[None]):
                StitchRequestHandler.do_GET(mock_handler)
            self.assertTrue(mock_handler.send_response.called)
            self.assertTrue(mock_handler.wfile.write.called)
            server.stop()
            return

        try:
            import requests

            # 1. SSE & Re-sync Coverage (Mock-based to avoid hangs)
            from warm_logic.kernel.substrate.stitch_server import (
                StitchRequestHandler,
                _buffer_lock,
                _event_buffer,
            )

            # Fill buffer to test re-sync re-entry
            with _buffer_lock:
                _event_buffer.append((1, "test", {"data": 1}))

            # Use a mock handler with the real do_GET method
            # We don't use spec=StitchRequestHandler here because wfile is an instance attribute
            mock_handler = MagicMock()
            mock_handler.path = "/stream"
            mock_handler.headers = {"Last-Event-ID": "0"}
            mock_handler.server = MagicMock()
            mock_handler.client_address = ("127.0.0.1", 12345)

            # Test valid re-sync
            with patch("queue.Queue.get", side_effect=[None]):
                StitchRequestHandler.do_GET(mock_handler)

            # Test invalid re-sync ID
            mock_handler.headers = {"Last-Event-ID": "invalid"}
            with patch("queue.Queue.get", side_effect=[None]):
                StitchRequestHandler.do_GET(mock_handler)

            # Basic assertions to ensure mock was interacted with
            self.assertTrue(mock_handler.send_response.called)
            self.assertTrue(mock_handler.wfile.write.called)

            # 2. POST Validation
            url = f"http://127.0.0.1:{port}/test"
            self.assertEqual(requests.post(url, json={}).status_code, 401)
            self.assertEqual(
                requests.post(
                    url, json={}, headers={"X-Warm-ID": "k", "X-Warm-Sig": "s"}
                ).status_code,
                403,
            )

            with patch(
                "warm_logic.kernel.identity.kinetic_id.KineticIdentity.verify_intent",
                return_value=True,
            ):
                self.assertEqual(requests.post(url, json={}).status_code, 401)
                self.assertEqual(
                    requests.post(
                        url, json={}, headers={"X-Warm-ID": "k", "X-Warm-Sig": "s"}
                    ).status_code,
                    404,
                )

            # 3. Static & Error
            with patch("builtins.open", mock_open(read_data=b"ui")):
                self.assertEqual(
                    requests.get(f"http://127.0.0.1:{port}/").status_code, 200
                )
            self.assertEqual(
                requests.get(f"http://127.0.0.1:{port}/bogus").status_code, 404
            )

            # 4. Broadcast edges
            import warm_logic.kernel.substrate.stitch_server as ss

            mock_q = MagicMock()
            mock_q.put.side_effect = ss.queue.Full

            with ss._sub_lock:
                ss._subscribers.append(mock_q)

            # Broadcast outside the lock to avoid deadlock
            StitchServer.broadcast("full", {})

            with ss._sub_lock:
                ss._subscribers.clear()

            StitchServer.broadcast("none", {})

        finally:
            server.stop()

    def test_chaos_monkey_perfection(self):
        """Cover chaos_monkey.py: middleware logic."""
        ChaosMonkey.configure(enabled=True, drop_rate=1.0)
        wrapped = ChaosMonkey.apply_middleware(lambda p: p)
        with patch("random.random", return_value=0.0):
            self.assertIsNone(wrapped({"x": 1}))

        ChaosMonkey.configure(enabled=True, drop_rate=0.0, corruption_rate=1.0)
        with patch("random.random", return_value=0.1):
            corrupted = wrapped({"hash": "ok", "signature": "sig"})
            self.assertIn("DEADBEEF", corrupted["hash"])
            self.assertEqual(corrupted["signature"], "INVALID")

        self.assertEqual(wrapped("string"), "string")
        ChaosMonkey.configure(enabled=False)
        self.assertEqual(wrapped("any"), "any")

    def test_block_propagation_handler(self):
        """Cover remaining network_bridge logic."""
        bridge = NetworkBridge("node_b")
        handler = BlockPropagationHandler(bridge)
        handler.handle_block({"block_hash": "h1"})
        self.assertEqual(len(handler.get_pending_blocks()), 1)
        handler.clear_committed("h1")

        from warm_logic.kernel.substrate.network_bridge import register_block_handlers

        self.assertIsNotNone(register_block_handlers(bridge, MagicMock()))


if __name__ == "__main__":
    unittest.main()
