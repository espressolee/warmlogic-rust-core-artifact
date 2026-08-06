import asyncio
import hashlib
import logging
import os
import sys

# Standardize Paths
src = os.path.abspath("src")
if src not in sys.path:
    sys.path.insert(0, src)

# Force Disable Rust BEFORE anything else
import warm_logic.kernel.rust_loader

warm_logic.kernel.rust_loader.HAS_RUST_CORE = False

import warm_logic.kernel.mesh.dht as dht
from warm_logic.kernel.mesh.dht import Contact, RoutingTable

# Setup logger
logger = logging.getLogger("SovereignMesh")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def c_gen(name, pk=None):
    _pk = pk if pk else name.encode().ljust(32, b"\x00")
    nid = hashlib.sha3_256(_pk).digest()
    return Contact(
        node_id=nid, address="127.0.0.1", port=80, public_key=_pk, silicon_id="S"
    )


async def test_split():
    local_id = b"\xff" * 32
    rt = RoutingTable(local_id)
    print(f"USE RUST: {rt._use_rust}")

    pk1 = b"P1".ljust(32, b"\x00")
    actual_id = hashlib.sha3_256(pk1).digest()
    c1 = Contact(node_id=actual_id, address="1", port=1, public_key=pk1, silicon_id="S")

    print(f">>> TEST START")
    await rt.update(c1)
    print(f">>> TEST END")
    print(f"Contacts: {len(rt.buckets[0].contacts)}")


if __name__ == "__main__":
    asyncio.run(test_split())
