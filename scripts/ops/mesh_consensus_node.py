"""Simulated Mesh Consensus Node."""

import argparse
import json
import os
import sys
import time

sys.path.append(os.getcwd())

# from warm_logic.kernel.consensus.p2p_transport import SwarmMessage # noqa: F401
from warm_logic.kernel.security.witness import WitnessSignature


def run_node(node_id: str):
    print(f"[Mesh Node] {node_id} active and listening for consensus requests...")

    # In a real implementation, this would connect to the P2P mesh.
    # Here we provide a helper to generate a signature for testing.

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            data = json.loads(line)
            if data.get("type") == "VETO_CHECK_REQUEST":
                run_id = data["payload"]["run_id"]
                target_hash = data["payload"]["target_hash"]

                # Sign the request
                sig = {
                    "witness_id": node_id,
                    "signature": f"SIG_{node_id}_{run_id}_{target_hash}",
                    "timestamp": time.time(),
                    "metadata": {"node_type": "mesh_sovereign"},
                }

                response = {
                    "type": "VETO_CHECK_RESPONSE",
                    "sender": node_id,
                    "payload": sig,
                }
                print(json.dumps(response))
                sys.stdout.flush()
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-id", required=True)
    args = parser.parse_args()
    run_node(args.node_id)
