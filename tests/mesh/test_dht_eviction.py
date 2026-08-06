import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

import warm_logic.kernel.mesh.dht
from warm_logic.kernel.mesh.dht import Contact, SovereignDHT


class TestKademliaResilience(unittest.IsolatedAsyncioTestCase):
    async def test_bucket_eviction_logic(self):
        # 1. Setup DHT with K_PARAM=2
        node_id = b"\x00" * 32  # local_id is 0
        dht = SovereignDHT(node_id, "127.0.0.1", 9000)

        warm_logic.kernel.mesh.dht.K_PARAM = 2
        dht.routing._use_rust = False
        dht.routing._verify_binding = MagicMock(return_value=True)

        # 2. Add high-bit nodes to fill the upper bucket
        # High-bit range: [2**255, 2**256-1]
        c1 = Contact(
            (0x80).to_bytes(1, "big") + b"\x01" * 31, "1.1.1.1", 1111, public_key=b"pk1"
        )
        c2 = Contact(
            (0x80).to_bytes(1, "big") + b"\x02" * 31, "2.2.2.2", 2222, public_key=b"pk2"
        )

        await dht.routing.update(c1, dht=dht)
        await dht.routing.update(c2, dht=dht)

        # At this point, bucket 0 (0 to 2**256) contains [c1, c2].
        # Adding any node near local_id (0) will trigger a split.
        c_local = Contact(b"\x00" * 31 + b"\x01", "0.0.0.1", 1)
        await dht.routing.update(c_local, dht=dht)

        # Now we should have 2 buckets:
        #   [0, 2**255-1] (contains local_id 0 and c_local)
        #   [2**255, 2**256-1] (contains c1, c2 - this is our target)

        self.assertEqual(len(dht.routing.buckets), 2)
        target_bucket = dht.routing.buckets[1]
        self.assertEqual(len(target_bucket.contacts), 2)
        self.assertEqual(target_bucket.contacts[0], c1)  # Oldest

        # 3. Add c3 (also high-bit) -> ALIVE scenario
        c3 = Contact(
            (0x80).to_bytes(1, "big") + b"\x03" * 31, "3.3.3.3", 3333, public_key=b"pk3"
        )
        dht.ping = AsyncMock(return_value=True)

        await dht.routing.update(c3, dht=dht)

        self.assertEqual(len(target_bucket.contacts), 2)
        self.assertNotIn(c3, target_bucket.contacts)
        self.assertEqual(target_bucket.contacts[-1], c1)  # c1 moved to end

        # 4. Add c4 -> DEAD scenario
        c4 = Contact(
            (0x80).to_bytes(1, "big") + b"\x04" * 31, "4.4.4.4", 4444, public_key=b"pk4"
        )
        dht.ping = AsyncMock(return_value=False)

        await dht.routing.update(c4, dht=dht)

        self.assertEqual(len(target_bucket.contacts), 2)
        self.assertNotIn(c2, target_bucket.contacts)  # c2 (now oldest) evicted
        self.assertEqual(target_bucket.contacts[-1], c4)
        print("✅ [Resilience] Kademlia Eviction logic verified.")


if __name__ == "__main__":
    unittest.main()
