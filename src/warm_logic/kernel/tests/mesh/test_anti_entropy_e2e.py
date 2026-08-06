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
import logging
import unittest

from warm_logic.kernel.mesh.anti_entropy import AntiEntropyAgent
from warm_logic.kernel.mesh.dht import Contact, SovereignDHT

# Configure logging to capture DHT/AntiEntropy logs during test
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TestE2E")


class TestAntiEntropyE2E(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _skip_if_socket_unavailable(exc: BaseException) -> None:
        if isinstance(exc, PermissionError):
            raise unittest.SkipTest(f"UDP sockets unavailable in this environment: {exc}")
        if isinstance(exc, OSError) and exc.errno in {errno.EPERM, errno.EACCES}:
            raise unittest.SkipTest(f"UDP sockets unavailable in this environment: {exc}")

    async def asyncSetUp(self):
        # Node 1: source of truth
        self.dht1 = SovereignDHT(b"\x01" * 32, "127.0.0.1", 0)
        self.state1 = {"key1": "data1", "key2": "data2"}
        self.agent1 = AntiEntropyAgent(
            dht=self.dht1,
            get_local_state=lambda: {
                k: v for k, v in self.state1.items()
            },  # In reality hashes, but simplifying
            apply_remote_record=self._apply1,
        )
        self.dht1.anti_entropy_agent = self.agent1  # Attach for RPC handlers
        try:
            await self.dht1.start()
        except (PermissionError, OSError) as exc:
            self._skip_if_socket_unavailable(exc)
            raise
        # [Fix] Update port to actual bound port
        if self.dht1.transport:
            self.dht1.port = self.dht1.transport.get_port()

        # Node 2: empty state
        self.dht2 = SovereignDHT(b"\x02" * 32, "127.0.0.1", 0)
        self.state2 = {}
        self.agent2 = AntiEntropyAgent(
            dht=self.dht2,
            get_local_state=lambda: {k: v for k, v in self.state2.items()},
            apply_remote_record=self._apply2,
        )
        self.dht2.anti_entropy_agent = self.agent2
        try:
            await self.dht2.start()
        except (PermissionError, OSError) as exc:
            self._skip_if_socket_unavailable(exc)
            raise
        # [Fix] Update port to actual bound port
        if self.dht2.transport:
            self.dht2.port = self.dht2.transport.get_port()

    async def asyncTearDown(self):
        if self.dht1.server:
            self.dht1.server.close()
        if self.dht2.server:
            self.dht2.server.close()
        # Give some time for sockets to close
        await asyncio.sleep(0.1)

    def _apply1(self, key, data):
        self.state1[key] = data
        return True

    def _apply2(self, key, data):
        self.state2[key] = data
        return True

    async def test_real_rpc_sync(self):
        logger.info("Starting RPC Sync Test...")

        # 1. Verify initial mismatch
        self.assertNotEqual(self.state1, self.state2)

        # 2. Trigger reconciliation from Agent2 (pull from Agent1)
        # We manually construct the Peer contact for DHT1
        peer_contact = Contact(self.dht1.node_id, "127.0.0.1", self.dht1.port)

        synced_count = await self.agent2.reconcile(peer_contact)

        # 3. Assertions
        logger.info(f"Synced {synced_count} records.")
        # Due to simplified "return all records" strategy in DHT, we might get duplicates
        self.assertTrue(synced_count >= 2)
        self.assertEqual(self.state2, self.state1)
        self.assertEqual(self.state2["key1"], "data1")

        # 4. Verify stat update
        self.assertEqual(self.agent2._stats.reconciliations_successful, 1)


if __name__ == "__main__":
    unittest.main()
