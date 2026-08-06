import asyncio
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.mesh.dht import SovereignDHT
from warm_logic.kernel.mesh.gossip import GossipAgent


class TestReflexArc(unittest.TestCase):
    def test_reflex_broadcast(self):
        """Verify reflex_broadcast iterates contacts and sends UDP."""
        # 1. Mock DHT and Routing
        mock_dht = MagicMock(spec=SovereignDHT)
        mock_routing = MagicMock()
        mock_bucket = MagicMock()

        # Mock contacts
        c1 = MagicMock()
        c1.address = ("127.0.0.1", 8001)
        c2 = MagicMock()
        c2.address = None
        c2.ip = "127.0.0.1"
        c2.port = 8002

        mock_bucket.get_nodes.return_value = [c1, c2]
        mock_routing.buckets = [mock_bucket]
        mock_dht.routing = mock_routing

        agent = GossipAgent(mock_dht)

        # 2. Fire Reflex Arc
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = mock_sock_cls.return_value
            count = agent.reflex_broadcast(b"VETO_SIGNAL")

            # 3. Verify
            self.assertEqual(count, 2)
            mock_sock.sendto.assert_any_call(b"VETO_SIGNAL", ("127.0.0.1", 8001))
            mock_sock.sendto.assert_any_call(b"VETO_SIGNAL", ("127.0.0.1", 8002))


if __name__ == "__main__":
    unittest.main()
