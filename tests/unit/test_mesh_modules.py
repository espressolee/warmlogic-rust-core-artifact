"""
Mesh Module Unit Tests.

P3xx: Comprehensive tests for mesh/peers.py, mesh/sync.py, mesh/topology.py.
Target: 80%+ coverage for mesh modules.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.mesh.peers import PeerInfo, PeerManager
from warm_logic.mesh.topology import NetworkTopology


class TestPeerInfo:
    """Tests for PeerInfo dataclass."""

    def test_peer_info_creation(self):
        """Verify PeerInfo can be created with required fields."""
        peer = PeerInfo(node_id="node-123", http_port=8000, address="192.168.1.1")

        assert peer.node_id == "node-123"
        assert peer.http_port == 8000
        assert peer.address == "192.168.1.1"
        assert peer.last_seen > 0

    def test_peer_is_alive_within_ttl(self):
        """Verify peer is alive within TTL window."""
        peer = PeerInfo(node_id="node-123", http_port=8000, address="192.168.1.1")

        assert peer.is_alive(ttl_seconds=15.0) is True

    def test_peer_is_dead_after_ttl(self):
        """Verify peer is dead after TTL expires."""
        peer = PeerInfo(
            node_id="node-123",
            http_port=8000,
            address="192.168.1.1",
            last_seen=time.time() - 20.0,  # 20 seconds ago
        )

        assert peer.is_alive(ttl_seconds=15.0) is False

    def test_peer_custom_ttl(self):
        """Verify custom TTL values work correctly."""
        peer = PeerInfo(
            node_id="node-123",
            http_port=8000,
            address="192.168.1.1",
            last_seen=time.time() - 5.0,
        )

        assert peer.is_alive(ttl_seconds=10.0) is True
        assert peer.is_alive(ttl_seconds=3.0) is False


class TestPeerManager:
    """Tests for PeerManager class."""

    def test_register_new_peer(self):
        """Verify new peer registration works."""
        manager = PeerManager(ttl_seconds=15.0)

        manager.register_peer("node-abc", "10.0.0.1", 8001)

        peers = manager.get_active_peers()
        assert len(peers) == 1
        assert peers[0].node_id == "node-abc"
        assert peers[0].address == "10.0.0.1"

    def test_update_existing_peer(self):
        """Verify existing peer update refreshes last_seen."""
        manager = PeerManager(ttl_seconds=15.0)

        manager.register_peer("node-abc", "10.0.0.1", 8001)
        time.sleep(0.1)
        manager.register_peer("node-abc", "10.0.0.2", 8002)  # Update

        peers = manager.get_active_peers()
        assert len(peers) == 1
        assert peers[0].address == "10.0.0.2"
        assert peers[0].http_port == 8002

    def test_ignore_self_registration(self):
        """Verify manager ignores self-registration."""
        manager = PeerManager(ttl_seconds=15.0)
        manager.set_local_id("my-node-id")

        manager.register_peer("my-node-id", "127.0.0.1", 8000)

        peers = manager.get_active_peers()
        assert len(peers) == 0

    def test_get_peer_count(self):
        """Verify peer count is accurate."""
        manager = PeerManager(ttl_seconds=15.0)

        manager.register_peer("node-1", "10.0.0.1", 8001)
        manager.register_peer("node-2", "10.0.0.2", 8002)
        manager.register_peer("node-3", "10.0.0.3", 8003)

        assert manager.get_peer_count() == 3

    def test_expired_peers_removed(self):
        """Verify expired peers are cleaned up."""
        manager = PeerManager(ttl_seconds=0.1)  # Very short TTL

        manager.register_peer("node-expire", "10.0.0.1", 8001)
        time.sleep(0.2)  # Wait for expiry

        peers = manager.get_active_peers()
        assert len(peers) == 0

    def test_thread_safety(self):
        """Verify manager is thread-safe."""
        manager = PeerManager(ttl_seconds=15.0)
        errors = []

        def register_peers(start_id: int):
            try:
                for i in range(10):
                    manager.register_peer(
                        f"node-{start_id}-{i}", f"10.0.{start_id}.{i}", 8000
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_peers, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert manager.get_peer_count() == 50


class TestNetworkTopology:
    """Tests for NetworkTopology singleton."""

    def test_singleton_pattern(self):
        """Verify NetworkTopology is a singleton."""
        t1 = NetworkTopology()
        t2 = NetworkTopology()

        assert t1 is t2

    def test_region_constants(self):
        """Verify region constants are defined."""
        assert NetworkTopology.US_EAST == "US-EAST"
        assert NetworkTopology.EU_WEST == "EU-WEST"
        assert NetworkTopology.AP_NORTH == "AP-NORTH"

    def test_latency_matrix_structure(self):
        """Verify latency matrix is complete."""
        matrix = NetworkTopology.LATENCY_MATRIX

        assert NetworkTopology.US_EAST in matrix
        assert NetworkTopology.EU_WEST in matrix
        assert NetworkTopology.AP_NORTH in matrix

        # Each region should have latency to all regions
        for region in [
            NetworkTopology.US_EAST,
            NetworkTopology.EU_WEST,
            NetworkTopology.AP_NORTH,
        ]:
            assert NetworkTopology.US_EAST in matrix[region]
            assert NetworkTopology.EU_WEST in matrix[region]
            assert NetworkTopology.AP_NORTH in matrix[region]

    def test_same_region_low_latency(self):
        """Verify same-region latency is low."""
        latency = NetworkTopology.get_latency_between_regions(
            NetworkTopology.US_EAST, NetworkTopology.US_EAST
        )
        assert latency == 5

    def test_cross_region_latency(self):
        """Verify cross-region latency is higher."""
        latency = NetworkTopology.get_latency_between_regions(
            NetworkTopology.US_EAST, NetworkTopology.EU_WEST
        )
        assert latency == 100

        latency_ap = NetworkTopology.get_latency_between_regions(
            NetworkTopology.US_EAST, NetworkTopology.AP_NORTH
        )
        assert latency_ap == 200

    def test_register_node(self):
        """Verify node registration works."""
        node_id = b"test-node-123"
        NetworkTopology.register_node(node_id, NetworkTopology.EU_WEST)

        region = NetworkTopology.get_region_for_id(node_id)
        assert region == NetworkTopology.EU_WEST

    def test_register_invalid_region_raises(self):
        """Verify invalid region registration raises error."""
        with pytest.raises(ValueError, match="Unknown region"):
            NetworkTopology.register_node(b"bad-node", "INVALID-REGION")

    def test_set_local_region(self):
        """Verify local region can be set."""
        NetworkTopology.set_local_region(NetworkTopology.AP_NORTH)
        topology = NetworkTopology()
        assert topology.local_region == NetworkTopology.AP_NORTH

    def test_set_invalid_local_region_raises(self):
        """Verify invalid local region raises error."""
        with pytest.raises(ValueError, match="Unknown region"):
            NetworkTopology.set_local_region("MARS")

    def test_get_latency_between_nodes(self):
        """Verify node-to-node latency calculation."""
        node_a = b"node-a-us"
        node_b = b"node-b-eu"

        NetworkTopology.register_node(node_a, NetworkTopology.US_EAST)
        NetworkTopology.register_node(node_b, NetworkTopology.EU_WEST)

        latency = NetworkTopology.get_latency_between_nodes(node_a, node_b)
        assert latency == 100

    def test_get_latency_alias(self):
        """Verify get_latency is alias for get_latency_between_nodes."""
        node_a = b"alias-test-a"
        node_b = b"alias-test-b"

        NetworkTopology.register_node(node_a, NetworkTopology.US_EAST)
        NetworkTopology.register_node(node_b, NetworkTopology.US_EAST)

        latency1 = NetworkTopology.get_latency(node_a, node_b)
        latency2 = NetworkTopology.get_latency_between_nodes(node_a, node_b)
        assert latency1 == latency2

    def test_unknown_node_defaults_to_us_east(self):
        """Verify unknown nodes default to US-EAST region."""
        unknown_node = b"completely-unknown-node"
        region = NetworkTopology.get_region_for_id(unknown_node)
        assert region == NetworkTopology.US_EAST


class TestSocialSyncAgent:
    """Tests for SocialSyncAgent class."""

    def test_agent_creation(self):
        """Verify agent can be created."""
        from warm_logic.mesh.sync import SocialSyncAgent

        mock_peer_manager = MagicMock()
        mock_social_store = MagicMock()

        agent = SocialSyncAgent(mock_peer_manager, mock_social_store)

        assert agent.peer_manager is mock_peer_manager
        assert agent.social_store is mock_social_store
        assert agent._running is False

    def test_agent_start_stop(self):
        """Verify agent start/stop lifecycle."""
        from warm_logic.mesh.sync import SocialSyncAgent

        mock_peer_manager = MagicMock()
        mock_peer_manager.get_active_peers.return_value = []
        mock_social_store = MagicMock()

        agent = SocialSyncAgent(mock_peer_manager, mock_social_store)

        agent.start()
        assert agent._running is True
        assert agent._thread is not None

        agent.stop()
        assert agent._running is False

    def test_agent_double_start_ignored(self):
        """Verify double start is ignored."""
        from warm_logic.mesh.sync import SocialSyncAgent

        mock_peer_manager = MagicMock()
        mock_peer_manager.get_active_peers.return_value = []
        mock_social_store = MagicMock()

        agent = SocialSyncAgent(mock_peer_manager, mock_social_store)

        agent.start()
        first_thread = agent._thread

        agent.start()  # Second start should be ignored
        assert agent._thread is first_thread

        agent.stop()

    def test_agent_get_stats(self):
        """Verify stats retrieval works."""
        from warm_logic.mesh.sync import SocialSyncAgent

        mock_peer_manager = MagicMock()
        mock_peer_manager.get_peer_count.return_value = 5
        mock_social_store = MagicMock()

        agent = SocialSyncAgent(mock_peer_manager, mock_social_store)
        agent._sync_count = 10
        agent._last_sync_peer = "peer-xyz"

        stats = agent.get_stats()

        assert stats["sync_count"] == 10
        assert stats["last_peer"] == "peer-xyz"
        assert stats["active_peers"] == 5


class TestSovereignDaemon:
    """Tests for SovereignDaemon tick() helper methods."""

    def test_autonomy_level_community(self):
        """Verify community edition has level 3 autonomy."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "warm_logic.app.cli.sovereign_daemon.SovereignDaemon._verify_enterprise_status",
                return_value=False,
            ):
                from warm_logic.app.cli.sovereign_daemon import SovereignDaemon

                daemon = SovereignDaemon("task.md", single_run=True)
                assert daemon.autonomy_level == 3

    def test_autonomy_level_enterprise(self):
        """Verify enterprise edition has level 5 autonomy."""
        with patch.dict(
            "os.environ", {"WARM_LOGIC_LICENSE_KEY": "WL-ENT-123"}, clear=False
        ):
            with patch(
                "warm_logic.app.cli.sovereign_daemon.SovereignDaemon._verify_enterprise_status",
                return_value=True,
            ):
                from warm_logic.app.cli.sovereign_daemon import SovereignDaemon

                daemon = SovereignDaemon("task.md", single_run=True)
                assert daemon.autonomy_level == 5
