import hashlib
import os
import sys

from warm_logic.kernel.mesh.dht import Contact, RoutingTable


def test_raw():
    local_id = b"\xff" * 32
    rt = RoutingTable(local_id)
    c_fail = Contact(node_id=b"0" * 32, address="trigger_binding_fail", port=1)
    print("CALLING _verify_binding...")
    rt._verify_binding(c_fail)
    print("DONE.")


if __name__ == "__main__":
    test_raw()
