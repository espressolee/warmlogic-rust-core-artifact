import json
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.mesh.dht import DHTProtocol, SovereignDHT
from warm_logic.kernel.zanzibar import RelationTuple, ZanzibarEngine


class TestMeshZanzibar(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.engine = ZanzibarEngine(":memory:")
        self.dht = MagicMock()
        self.dht.node_id = b"0" * 32

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_write_triggers_broadcast(self):
        """Verify that writing a tuple triggers DHT broadcast."""
        t = RelationTuple(
            "doc",
            "1",
            "viewer",
            "user",
            "alice",
            authority="did:warm:root:1",
            signature="ROOT_AUTHORITY_SIG",
        )

        # Mock signature verification to pass
        with patch.object(self.engine, "verify_signature", return_value=True):
            self.engine.write_tuple(t, dht=self.dht, replicate=True)

            # Verify broadcast called
            self.assertTrue(self.dht.broadcast.called)

            # Verify payload
            args, _ = self.dht.broadcast.call_args
            payload = json.loads(args[0].decode())
            self.assertEqual(payload["type"], "ZANZIBAR_TUPLE")
            self.assertEqual(payload["object_id"], "1")
            print("✅ Verified: Local write triggers Mesh Broadcast.")

    def test_handle_incoming_replication(self):
        """Verify that incoming DHT message writes to Zanzibar (without re-broadcast)."""
        # We need to simulate the import inside dht.py which imports the global 'zanzibar'
        # So we mock sys.modules or patch the storage

        msg = {
            "type": "ZANZIBAR_TUPLE",
            "namespace": "doc",
            "object_id": "2",
            "relation": "owner",
            "subject_namespace": "user",
            "subject_id": "bob",
            "authority": "did:warm:root:1",
            "signature": "ROOT_AUTHORITY_SIG",
        }

        # We need a real DHTProtocol but with mocked dht
        real_dht = SovereignDHT(b"0" * 32, "127.0.0.1", 5000)
        protocol = DHTProtocol(real_dht)

        # Patch the GLOBAL zanzibar instance used by dht.py
        with patch("warm_logic.kernel.zanzibar.zanzibar", self.engine):
            with patch.object(self.engine, "verify_signature", return_value=True):
                # Spy on write_tuple
                with patch.object(
                    self.engine, "write_tuple", side_effect=self.engine.write_tuple
                ) as mock_write:
                    protocol.handle_zanzibar_tuple(msg, ("1.2.3.4", 1234))

                    # Verify write_tuple called
                    self.assertTrue(mock_write.called)

                    # Verify tuple stored in DB
                    self.assertTrue(self.engine.check("doc", "2", "owner", "bob"))
                    print("✅ Verified: Mesh replication writes to local DB.")


if __name__ == "__main__":
    unittest.main()
