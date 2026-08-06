import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

from warm_logic.kernel.substrate.proof_zk import ZKProofGenerator
from warm_logic.kernel.sys.persistence import SovereignStore


def backfill_missing_proofs():
    store = SovereignStore()
    print("Starting Retroactive ZK Proof Backfill...")

    # Identify blocks missing proofs
    cursor = store.conn.execute(
        "SELECT * FROM blocks WHERE zk_proof IS NULL OR zk_proof = '' ORDER BY id ASC"
    )
    blocks = cursor.fetchall()

    if not blocks:
        print("No missing proofs found.")
        return

    print(f"Found {len(blocks)} blocks requiring proofs.")

    for block in blocks:
        block_id = block["id"]
        block_hash = block["hash"]
        prev_hash = block["prev_hash"]

        # Determine column name for txs
        cursor_info = store.conn.execute("PRAGMA table_info(blocks)")
        columns = [row["name"] for row in cursor_info.fetchall()]
        tx_col = "tx_ids" if "tx_ids" in columns else "transactions"

        txs = json.loads(block[tx_col])

        # Generate a retroactive proof
        # For backfill, we use the stored hash as the 'new_state_root' surrogate
        # if actual roots weren't captured for legacy blocks.
        proof = ZKProofGenerator.generate_proof(
            prev_state_root=prev_hash,
            transactions=txs,
            new_state_root=block_hash,
            prev_proof=None,  # Legacy blocks don't have recursive roots
        )

        proof_json = json.dumps(proof)

        # Attach to block
        store.conn.execute(
            "UPDATE blocks SET zk_proof = ? WHERE id = ?", (proof_json, block_id)
        )
        store.conn.commit()
        print(f"  Backfilled block {block_id} ({block_hash[:8]})")

    print("Backfill Complete.")


if __name__ == "__main__":
    backfill_missing_proofs()
