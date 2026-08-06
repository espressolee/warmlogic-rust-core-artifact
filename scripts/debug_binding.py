import asyncio
import hashlib
from unittest.mock import MagicMock, patch

from warm_logic.kernel.mesh.dht import Contact, RoutingTable


async def debug_binding():
    local_id = b"\xff" * 32
    # Ensure HAS_RUST_CORE is False to use Python logic
    with patch("warm_logic.kernel.mesh.dht.rust_loader.HAS_RUST_CORE", False):
        rt = RoutingTable(local_id)
        pk = b"FAIL_ADDR".ljust(32, b"\x00")
        nid = hashlib.sha3_256(pk).digest()
        c = Contact(node_id=nid, address="trigger_binding_fail", port=80, public_key=pk)

        print(f"DEBUG: Calling rt.update with address={c.address}")
        res = await rt.update(c)
        print(f"DEBUG: rt.update returned {res}")


if __name__ == "__main__":
    asyncio.run(debug_binding())
