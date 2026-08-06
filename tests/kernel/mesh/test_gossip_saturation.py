import asyncio
import json
import time
import unittest
import sys
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

# Pre-emptive sys.modules patching for dependencies
mock_crypto = MagicMock()
mock_dht_module = MagicMock()
mock_provenance = MagicMock()
mock_topology = MagicMock()

patcher = patch.dict(
    "sys.modules",
    {
        "warm_logic.kernel.sys.cryptography": mock_crypto,
        "warm_logic.kernel.mesh.dht": mock_dht_module,
        "warm_logic.kernel.provenance": mock_provenance,
        "warm_logic.mesh.topology": mock_topology,
    },
)
# Scope dependency poisoning to gossip module import only.
patcher.start()

from warm_logic.kernel.mesh.gossip import (
    GossipAgent,
    GossipStats,
    ManifestRecord,
    ThermalThrottler,
)
patcher.stop()

# Keep imported module patchable even if global patcher scope ended.
import warm_logic.kernel.mesh.gossip as gossip_module


class TestGossipSaturation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_dht = MagicMock()
        self.mock_dht.node_id.hex.return_value = "node_id_hex"
        self.mock_dht.public_key.hex.return_value = "pub_key_hex"
        self.mock_dht.private_key = "priv_key"
        self.mock_dht.routing.find_neighbors.return_value = []

        self.mock_codebase = MagicMock()
        self.mock_codebase.generate_manifest.return_value = "local_hash"

        # Ensure MLDSA sign returns a string (JSON serializable)
        mock_crypto.MLDSA.return_value.sign.return_value = "signature_hex"

        # Order-independent: always patch MLDSA on the actual imported gossip module.
        self._mldsa_patcher = patch.object(gossip_module, "MLDSA")
        self.mock_mldsa_cls = self._mldsa_patcher.start()
        self.addCleanup(self._mldsa_patcher.stop)
        # Keep pre-import mock and runtime module patch aligned.
        mock_crypto.MLDSA.return_value = self.mock_mldsa_cls.return_value
        self.mock_mldsa_cls.return_value.sign.return_value = "signature_hex"
        self.mock_mldsa_cls.return_value.verify.return_value = True

        self.agent = GossipAgent(
            dht=self.mock_dht,
            codebase=self.mock_codebase,
        )

    # --- Thermal Throttler Tests ---

    def test_thermal_reading_normal(self):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="45000")):  # 45 C
                temp = ThermalThrottler.get_temperature()
                self.assertEqual(temp, 45.0)
                delay = ThermalThrottler.get_gossip_delay(5.0)
                self.assertEqual(delay, 5.0)

    def test_thermal_reading_critical(self):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="80000")):  # 80 C
                temp = ThermalThrottler.get_temperature()
                self.assertEqual(temp, 80.0)
                delay = ThermalThrottler.get_gossip_delay(5.0)
                self.assertEqual(delay, 20.0)  # 5.0 * 4

    def test_thermal_reading_failure(self):
        with patch("os.path.exists", return_value=False):
            temp = ThermalThrottler.get_temperature()
            self.assertEqual(temp, 25.0)

    # --- Agent Lifecycle ---

    async def test_start_stop(self):
        self.agent._gossip_loop = AsyncMock()
        await self.agent.start()
        self.assertTrue(self.agent._running)
        self.assertIsNotNone(self.agent._task)

        # Start again should be no-op
        task = self.agent._task
        await self.agent.start()
        self.assertIs(self.agent._task, task)

        await self.agent.stop()
        self.assertFalse(self.agent._running)
        self.agent._gossip_loop.assert_called()

    # --- Announce Manifest ---

    async def test_announce_manifest_basic(self):
        # Setup mocks
        self.mock_mldsa_cls.return_value.sign.return_value = "sig"
        c1 = MagicMock()
        c1.node_id.hex.return_value = "peer1"
        self.mock_dht.routing.find_neighbors.return_value = [c1]

        # Override public_key.hex again just in case
        self.mock_dht.public_key.hex.return_value = "pub_key_hex"

        count = await self.agent.announce_manifest()

        self.assertEqual(count, 1)
        self.mock_dht.send.assert_called_once()
        args = self.mock_dht.send.call_args[0]
        payload = json.loads(args[1])
        self.assertEqual(payload["type"], "MANIFEST_ANNOUNCE")
        self.assertEqual(payload["manifest_hash"], "local_hash")
        self.assertEqual(payload["signature"], "sig")

    async def test_announce_manifest_no_hash(self):
        self.agent._local_hash = None
        self.agent.codebase = None  # Prevent generation
        count = await self.agent.announce_manifest()
        self.assertEqual(count, 0)

    async def test_announce_galaxy_topology(self):
        """Test region-biased routing."""
        self.agent.dht.galaxy = MagicMock()  # Enable galaxy mode

        c_local = MagicMock()
        c_local.node_id.hex.return_value = "local"
        c_remote = MagicMock()
        c_remote.node_id.hex.return_value = "remote"

        self.mock_dht.routing.find_neighbors.return_value = [c_local, c_remote]

        # Ensure sign works
        self.mock_mldsa_cls.return_value.sign.return_value = "sig"

        # Mock _is_same_region via patch
        with patch.object(self.agent, "_is_same_region") as mock_same:
            mock_same.side_effect = lambda c: c == c_local

            # We need >3 remote peers to trigger sampling, let's just test basic separation
            await self.agent.announce_manifest()

            # Should optimize order or count
            self.assertEqual(self.mock_dht.send.call_count, 2)

    # --- Receive Manifest ---

    def test_receive_manifest_verified(self):
        self.mock_mldsa_cls.return_value.verify.return_value = True

        res = self.agent.on_receive_manifest(
            sender_id="peer1",
            manifest_hash="local_hash",
            timestamp=123.0,
            signature="sig",
            sender_pk_hex="pk",
        )
        self.assertTrue(res)
        self.assertIn("peer1", self.agent._received_manifests)
        self.assertTrue(self.agent._received_manifests["peer1"].verified)

    def test_receive_manifest_invalid_sig(self):
        self.mock_mldsa_cls.return_value.verify.return_value = False

        res = self.agent.on_receive_manifest(
            sender_id="peer1",
            manifest_hash="hash",
            timestamp=123.0,
            signature="bad_sig",
            sender_pk_hex="pk",
        )
        self.assertFalse(res)
        self.assertNotIn("peer1", self.agent._received_manifests)

    def test_receive_manifest_mismatch(self):
        self.mock_mldsa_cls.return_value.verify.return_value = True

        # Capture mismatch callback
        callback = MagicMock()
        self.agent._on_consensus_mismatch = callback

        res = self.agent.on_receive_manifest(
            sender_id="peer1",
            manifest_hash="other_hash",
            timestamp=123.0,
            signature="sig",
            sender_pk_hex="pk",
        )
        self.assertFalse(res)  # Mismatch returns False for 'verified' against local?

        callback.assert_called_with("peer1", "other_hash", "local_hash")

    # --- Consensus ---

    def test_check_consensus(self):
        self.agent._received_manifests = {
            "p1": ManifestRecord("p1", "hash1", 0),
            "p2": ManifestRecord("p2", "hash1", 0),
            "p3": ManifestRecord("p3", "hash2", 0),
        }
        self.agent.set_local_hash("hash1")

        res = self.agent.check_consensus()

        self.assertFalse(res["has_consensus"])  # 3 vs 1. Wait.
        # Total = 3 peers + 1 local = 4.
        # hash1: 2 peers + 1 local = 3.
        # hash2: 1 peer.
        # Majority is hash1 (count 3). 3 != 4. No consensus.

        self.assertEqual(res["majority_hash"], "hash1")
        self.assertEqual(len(res["deviants"]), 1)
        self.assertEqual(res["deviants"][0]["sender_id"], "p3")

    # --- Reflex Arc ---

    def test_reflex_broadcast(self):
        # Mock contacts in buckets
        c1 = MagicMock()
        c1.address = ("1.1.1.1", 8000)
        bucket = MagicMock()
        bucket.get_nodes.return_value = [c1]
        self.mock_dht.routing.buckets = [bucket]

        with patch("socket.socket") as mock_sock_cls:
            mock_sock = mock_sock_cls.return_value
            count = self.agent.reflex_broadcast(b"data")

            self.assertEqual(count, 1)
            mock_sock.sendto.assert_called_with(b"data", ("1.1.1.1", 8000))

    async def test_announce_insight_critical(self):
        # Should trigger reflex
        with patch.object(self.agent, "reflex_broadcast") as mock_reflex:
            await self.agent.announce_insight({"id": "i1"}, priority="critical")
            mock_reflex.assert_called()

    # --- Integration / Other ---

    def test_is_same_region_logic(self):
        c = MagicMock()
        c.node_id = b"peer-1"
        self.mock_dht.node_id = b"self-1"

        mock_topology.NetworkTopology.get_latency.return_value = 10.0
        with patch.dict(sys.modules, {"warm_logic.mesh.topology": mock_topology}):
            self.assertTrue(self.agent._is_same_region(c))

        mock_topology.NetworkTopology.get_latency.return_value = 100.0
        with patch.dict(sys.modules, {"warm_logic.mesh.topology": mock_topology}):
            self.assertFalse(self.agent._is_same_region(c))

    async def test_gossip_loop_throttling(self):
        # Verify loop calls announce_manifest
        self.agent.announce_manifest = AsyncMock()

        # Override sleep to avoid delay
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Set running true
            self.agent._running = True
            # Loop runs: sleep, announce...
            # We want it to run once then stop.
            # If we raise CancelledError in sleep, it catches and breaks.
            mock_sleep.side_effect = [None, asyncio.CancelledError]

            await self.agent._gossip_loop()

            self.agent.announce_manifest.assert_called()
