import asyncio
import logging
import uuid
import json
from warm_logic.kernel.mesh.dht import SovereignDHT
from warm_logic.system.fleet.manager import FleetManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HiveVerify")

import hashlib

async def verify_policy_gossip():
    logger.info("[Hive] Starting Multi-Node Policy Sync Verification...")
    
    # Generate PQC-compliant Node A
    node_a_pk = b"PUBLIC_KEY_A"
    node_a_id = hashlib.sha256(node_a_pk).digest()
    node_a_fm = FleetManager()
    node_a_dht = SovereignDHT(node_a_id, "127.0.0.1", 9001, public_key=node_a_pk, db_path="sovereign_db_a")
    node_a_dht.fleet_manager = node_a_fm
    await node_a_dht.start()
    
    # Generate PQC-compliant Node B
    node_b_pk = b"PUBLIC_KEY_B"
    node_b_id = hashlib.sha256(node_b_pk).digest()
    node_b_fm = FleetManager()
    node_b_dht = SovereignDHT(node_b_id, "127.0.0.1", 9002, public_key=node_b_pk, db_path="sovereign_db_b")
    node_b_dht.fleet_manager = node_b_fm
    await node_b_dht.start()
    
    # Establish Mesh: Node B learns about Node A
    await node_b_dht.bootstrap([("127.0.0.1", 9001)])
    await asyncio.sleep(3) # Wait for discovery and PONG
    
    logger.info(f"Node A Routing Table: {[c.address + ':' + str(c.port) for c in node_a_dht.routing.get_all_contacts()]}")
    logger.info(f"Node B Routing Table: {[c.address + ':' + str(c.port) for c in node_b_dht.routing.get_all_contacts()]}")
    
    # Node A triggers a Hive Lockdown Policy
    invariant = "GLOBAL_LOCKDOWN"
    logger.info(f"Node A broadcasting {invariant}")
    node_a_dht.broadcast_policy_event(invariant, True)
    
    # Verification: Does Node B sync the state?
    logger.info("⏳ Waiting for Policy Gossip to converge...")
    for i in range(10):
        await asyncio.sleep(1)
        if node_b_fm.global_policies.get(invariant) is True:
            logger.info(f"[SUCCESS] Node B synchronized Hive Policy: {invariant} == TRUE (Trial {i+1})")
            break
    else:
        logger.error(f"[FAILURE] Node B failed to sync Hive Policy. Node B Policies: {node_b_fm.global_policies}")
        return False

    # Final cleanup
    if node_a_dht.transport:
        node_a_dht.transport.close()
    if node_b_dht.transport:
        node_b_dht.transport.close()
        
    return True

if __name__ == "__main__":
    asyncio.run(verify_policy_gossip())
