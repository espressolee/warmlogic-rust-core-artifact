import asyncio
import os
import sys

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath("src"))

import hashlib

from warm_logic.kernel.mesh.dht import Contact, RoutingTable


async def main():
    print("Initializing RoutingTable...")
    node_id = b"\xff" * 32
    rt = RoutingTable(node_id)

    print("Creating Contact with trigger_binding_fail...")
    c = Contact(b"\x00" * 32, "trigger_binding_fail", 80)

    print(f"Contact address: {c.address}")

    print("Calling update...")
    await rt.update(c)
    print("Update finished.")


if __name__ == "__main__":
    asyncio.run(main())
