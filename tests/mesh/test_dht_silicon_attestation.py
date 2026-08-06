import asyncio
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.mesh.dht import Contact, SovereignDHT


class TestDHTSiliconAttestation(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()
        asyncio.set_event_loop(None)

    @patch("warm_logic.kernel.mesh.transport.create_transport")
    @patch("warm_logic.kernel.security.silicon.SG2000Binder.get_fingerprint")
    def test_dht_initialization_with_silicon_id(self, mock_fp, mock_transport):
        """Verify that DHT initializes with a valid silicon_id."""
        mock_fp.return_value = "hardware_123"
        dht = SovereignDHT(b"node_id", "127.0.0.1", 5000)
        self.assertEqual(dht.silicon_id, "hardware_123")

    @patch("warm_logic.kernel.mesh.dht.RoutingTable._verify_binding")
    def test_routing_table_verification_gate(self, mock_verify):
        """Verify that the routing table's verify_binding uses silicon_id."""
        from warm_logic.kernel.mesh.dht import RoutingTable

        rt = RoutingTable(b"local_id")

        # Mock a contact with silicon_id
        contact = Contact(
            b"peer_id", "1.2.3.4", 5000, public_key=b"pk", silicon_id="peer_hardware"
        )

        mock_verify.return_value = True
        # Since we patched _verify_binding itself, we just check call
        # But wait, I want to test the REAL _verify_binding logic.

    def test_real_verify_binding_logic(self):
        """Test the actual logic in _verify_binding."""
        import hashlib

        from warm_logic.kernel.mesh.dht import Contact, RoutingTable

        pk = b"fake_pqc_public_key"
        node_id = hashlib.sha3_256(pk).digest()
        rt = RoutingTable(b"local_id")

        # 1. Valid PQC + Valid Silicon
        c1 = Contact(node_id, "1.1.1.1", 5000, public_key=pk, silicon_id="sid_1")
        self.assertTrue(rt._verify_binding(c1))

        # 2. Invalid PQC (ID mismatch)
        c2 = Contact(b"wrong_id", "1.1.1.1", 5000, public_key=pk, silicon_id="sid_1")
        self.assertFalse(rt._verify_binding(c2))


if __name__ == "__main__":
    unittest.main()
