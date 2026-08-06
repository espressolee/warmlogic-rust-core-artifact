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
import errno
import json
import logging
import sys
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.mesh.dht import SovereignDHT

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TestDHTZK")


class TestDHTZKStore(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _skip_if_socket_unavailable(exc: BaseException) -> None:
        if isinstance(exc, PermissionError):
            raise unittest.SkipTest(f"UDP sockets unavailable in this environment: {exc}")
        if isinstance(exc, OSError) and exc.errno in {errno.EPERM, errno.EACCES}:
            raise unittest.SkipTest(f"UDP sockets unavailable in this environment: {exc}")

    async def asyncSetUp(self):
        # Establish mock for warm_logic_rs BEFORE starting DHT
        self.mock_rs = MagicMock()
        self.patcher = patch.dict(sys.modules, {"warm_logic_rs": self.mock_rs})
        self.patcher.start()
        self.acl_patcher = patch(
            "warm_logic.kernel.mesh.dht.check_permission", return_value=True
        )
        self.acl_patcher.start()

        # Default: valid proof
        self.mock_rs.RustZKProofGenerator.return_value.verify_state_proof.return_value = True

        self.dht = SovereignDHT(b"\x01" * 32, "127.0.0.1", 0)
        try:
            await self.dht.start()
        except (PermissionError, OSError) as exc:
            self._skip_if_socket_unavailable(exc)
            raise

        # [Fix] Update port to actual bound port
        if self.dht.transport:
            self.dht.port = self.dht.transport.get_port()

        self.port = self.dht.port
        # Mock storage to verify calls
        self.dht.storage = MagicMock()
        # Make it behave like a dict for getitem too if needed, but we check calls mainly
        self.dht.storage.__getitem__.side_effect = lambda k: {"value": "mock_val"}

    async def asyncTearDown(self):
        if self.dht.transport:
            self.dht.transport.close()
        self.acl_patcher.stop()
        self.patcher.stop()
        await asyncio.sleep(0.1)

    async def test_store_with_valid_zk(self):
        """Store with valid ZK proof should succeed."""
        import os
        import time

        key = "test_key"
        value = "test_value"
        value_hash_int = int(str(time.time()).replace(".", "")[-8:])
        blinding = os.urandom(32).hex()

        # Generate fake proof via mocked RS
        zk_gen = self.mock_rs.RustZKProofGenerator()
        proof = zk_gen.generate_state_proof(value_hash_int, blinding)
        proof.proof_hex = "mock_proof_hex"
        proof.commitment_hex = "mock_commitment_hex"

        # Force verification success
        self.mock_rs.RustZKProofGenerator.return_value.verify_state_proof.return_value = True

        message = {
            "type": "STORE_VALUE",
            "sender_id": (b"\x02" * 32).hex(),
            "key": key,
            "value": value,
            "zk_proof": proof.proof_hex,
            "commitment": proof.commitment_hex,
            "msg_id": "req-valid-001",
        }

        # Send via UDP
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, remote_addr=("127.0.0.1", self.port)
        )
        transport.sendto(json.dumps(message).encode("utf-8"))
        await asyncio.sleep(0.2)
        transport.close()

        # Verify stored
        # Since storage is a MagicMock, key in storage fails. Check method call instead.
        # Payload is constructed inside handle_store_value_request
        # call_args[0][0] is key, call_args[0][1] is value payload
        self.dht.storage.put.assert_called()
        call_args = self.dht.storage.put.call_args
        self.assertEqual(call_args[0][0], key)
        self.assertIn(value, call_args[0][1])  # Payload is json string
        logger.info(f"Valid ZK store succeeded for key '{key}'")

    async def test_store_without_zk_rejected(self):
        """Store without ZK proof should be rejected."""
        key = "no_proof_key"
        value = "some_value"

        message = {
            "type": "STORE_VALUE",
            "sender_id": (b"\x03" * 32).hex(),
            "key": key,
            "value": value,
            # Missing zk_proof and commitment
            "msg_id": "req-no-proof-001",
        }

        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, remote_addr=("127.0.0.1", self.port)
        )
        transport.sendto(json.dumps(message).encode("utf-8"))
        await asyncio.sleep(0.2)
        transport.close()

        # Should NOT be stored
        self.dht.storage.put.assert_not_called()
        self.dht.storage.__setitem__.assert_not_called()
        logger.info("Store without ZK proof correctly rejected")

    async def test_store_with_invalid_zk_rejected(self):
        """Store with tampered ZK proof should be rejected."""
        import os
        import time

        key = "tampered_key"
        value = "tampered_value"
        value_hash_int = int(str(time.time()).replace(".", "")[-8:])
        blinding = os.urandom(32).hex()

        # Generate fake proof via mocked RS
        zk_gen = self.mock_rs.RustZKProofGenerator()
        proof = zk_gen.generate_state_proof(value_hash_int, blinding)
        proof.proof_hex = "val1:val2:val3"  # Needs colons for tampering logic
        proof.commitment_hex = "mock_commitment_hex"

        # Force verification failure for this test
        self.mock_rs.RustZKProofGenerator.return_value.verify_state_proof.return_value = False

        # Tamper with the proof
        parts = proof.proof_hex.split(":")
        parts[1] = "0" * len(parts[1])  # Zero out z1
        tampered_proof = ":".join(parts)

        message = {
            "type": "STORE_VALUE",
            "sender_id": (b"\x04" * 32).hex(),
            "key": key,
            "value": value,
            "zk_proof": tampered_proof,
            "commitment": proof.commitment_hex,
            "msg_id": "req-tamper-001",
        }

        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, remote_addr=("127.0.0.1", self.port)
        )
        transport.sendto(json.dumps(message).encode("utf-8"))
        await asyncio.sleep(0.2)
        transport.close()

        # Should NOT be stored
        self.dht.storage.put.assert_not_called()
        self.dht.storage.__setitem__.assert_not_called()
        logger.info("Store with tampered ZK proof correctly rejected")


if __name__ == "__main__":
    unittest.main()
