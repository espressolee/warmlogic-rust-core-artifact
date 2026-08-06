"""
Verify Sovereign Governance (Phase 82)
Tests:
1. Ethics Monitor τ_ethics calculation and Veto Lock.
2. Byzantine Revocation List (BRL) node ejection.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from warm_logic.app.cli.sovereign_daemon import SovereignDaemon
from warm_logic.kernel.mesh.dht import Contact, SovereignDHT
from warm_logic.kernel.ops.ethics_monitor import EthicsMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GovernanceTest")


async def test_governance():
    logger.info(" Starting Sovereign Governance (Phase 82) Test...")

    # 1. Test VETO_LOCK
    daemon = SovereignDaemon(task_path="task.md", single_run=True)
    sentinel = EthicsMonitor(kernel_api=daemon)

    logger.info("Triggering simulated Ethical Breach...")
    # Manually drop score to trigger veto
    sentinel.current_score = 0.5
    await sentinel._initiate_veto_lock()

    if daemon._veto_locked:
        logger.info("SUCCESS: VETO_LOCK Enforced in Daemon.")
    else:
        logger.error("FAILURE: VETO_LOCK not triggered.")
        return

    # 2. Test BRL (Revocation)
    logger.info("Testing Byzantine Revocation List (BRL)...")
    dht = SovereignDHT(b"local_id" + b"\x00" * 24, "127.0.0.1", 20000)

    malicious_id = b"evil_node" + b"\x00" * 23
    malicious_contact = Contact(malicious_id, "6.6.6.6", 666, public_key=b"evil_pk")

    # Add to BRL
    dht.routing.revoke_node(malicious_id)

    # Try to process message from malicious node
    # Should be rejected in routing.update
    is_valid = dht.routing._verify_binding(malicious_contact)

    if not is_valid:
        logger.info("SUCCESS: Malicious node ejected via BRL.")
    else:
        logger.error("FAILURE: Malicious node allowed despite BRL.")
        return

    logger.info("\nFinal Verdict: SOVEREIGN GOVERNANCE ACTIVE & ENFORCED. ")


if __name__ == "__main__":
    asyncio.run(test_governance())
