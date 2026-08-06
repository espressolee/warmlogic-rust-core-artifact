import asyncio
import json
import os
import shutil
import tempfile
import unittest

from warm_logic.kernel.mesh.dht import Contact, SovereignDHT
from warm_logic.kernel.mesh.gossip import GossipAgent
from warm_logic.kernel.ops.service_registry import ServiceQuorum
from warm_logic.kernel.sys.persistence import SovereignStore


class TestServiceGovernance(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.nodes = []
        self.stores = []
        self.registries = []
        self._in_process_relay = False

        # Setup 3 nodes with isolated directories
        for i in range(3):
            port = 10000 + i
            node_dir = os.path.join(self.tmp_dir, f"node_{i}")
            os.makedirs(node_dir, exist_ok=True)

            # 1. Main persistence store
            db_path = os.path.join(node_dir, "sovereign.db")
            store = SovereignStore(db_path)

            # 2. DHT instance (it handles its own storage at dht_db_path)
            dht_db_path = os.path.join(node_dir, "dht_db")
            dht = SovereignDHT(bytes([i] * 32), "127.0.0.1", port, db_path=dht_db_path)

            # 3. Registry & Gossip
            gossip = GossipAgent(dht)
            registry = ServiceQuorum(store, gossip)
            dht.service_registry = registry

            self.nodes.append(dht)
            self.stores.append(store)
            self.registries.append(registry)
            try:
                await dht.start()
            except OSError as exc:
                # Some CI/sandbox environments prohibit UDP bind/listen entirely.
                if getattr(exc, "errno", None) not in {1, 13}:
                    raise
                self._in_process_relay = True

        # Connect them manually
        for i in range(3):
            for j in range(3):
                if i != j:
                    c = Contact(self.nodes[j].node_id, "127.0.0.1", 10000 + j)
                    await self.nodes[i].routing.update(c, dht=self.nodes[i])

        if self._in_process_relay:
            self._install_in_process_relay()

    def _install_in_process_relay(self) -> None:
        """Route governance packets directly between local test nodes without UDP."""

        def make_broadcast(sender_idx: int):
            def _broadcast(message: bytes) -> int:
                payload = json.loads(message.decode("utf-8"))
                routed = 0
                for idx, registry in enumerate(self.registries):
                    if idx == sender_idx:
                        continue
                    msg_type = payload.get("type")
                    if msg_type == "SERVICE_REGISTRATION_PROPOSAL":
                        registry.on_receive_proposal(payload)
                        routed += 1
                    elif msg_type == "SERVICE_REGISTRATION_VOTE":
                        registry.on_receive_vote(
                            payload.get("voter_id", ""),
                            payload.get("proposal_id", ""),
                            bool(payload.get("vote", False)),
                        )
                        routed += 1
                return routed

            return _broadcast

        for idx, dht in enumerate(self.nodes):
            dht.broadcast = make_broadcast(idx)

    async def asyncTearDown(self):
        for dht in self.nodes:
            if dht.server:
                dht.server.close()
        for store in self.stores:
            store.close()
        shutil.rmtree(self.tmp_dir)

    async def test_service_registration_quorum(self):
        # 1. Node 0 proposes a service
        service_data = {
            "node_id": "SN-TEST-01",
            "endpoint": "localhost:9999",
            "capacity_gb": 1000,
        }

        print("🚀 Node 0 proposing service...")
        proposal_id = self.registries[0].propose_service(service_data)

        # 2. Give time for propagation and voting
        await asyncio.sleep(2.0)

        # 3. Verify that Node 0 persisted the service after quorum
        services = self.registries[0].get_verified_services()
        self.assertIn("SN-TEST-01", services)
        self.assertEqual(services["SN-TEST-01"]["endpoint"], "localhost:9999")
        print("✅ [Governance] Service registration quorum reached and verified.")


if __name__ == "__main__":
    unittest.main()
