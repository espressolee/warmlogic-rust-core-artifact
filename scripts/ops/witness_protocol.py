"""Utility for collecting and verifying witness signatures."""

import argparse
import json
import os
import sys
import time

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.kernel.security.witness import WitnessManager, WitnessSignature


def main():
    parser = argparse.ArgumentParser(
        description="Multi-signer Witness Protocol Utility"
    )
    parser.add_argument("--run-id", required=True, help="ID of the run to witness")
    parser.add_argument(
        "--target-hash", required=True, help="Hash of the artifact being witnessed"
    )
    parser.add_argument("--witness-id", help="ID of the witness")
    parser.add_argument("--sign", help="Signature string to add")
    parser.add_argument("--threshold", type=int, default=2, help="Consensus threshold")
    parser.add_argument(
        "--verify", action="store_true", help="Verify the witness bundle"
    )
    parser.add_argument("--output", help="Path to save the witness bundle")

    args = parser.parse_args()

    manager = WitnessManager(threshold=args.threshold)

    # Load existing bundle if output exists
    if args.output and os.path.exists(args.output):
        try:
            with open(args.output, "r") as f:
                data = json.load(f)
                bundle = manager.create_bundle(data["run_id"], data["target_hash"])
                bundle.threshold = data.get("threshold", args.threshold)
                for sig_data in data.get("signatures", []):
                    bundle.signatures.append(WitnessSignature(**sig_data))
        except Exception as e:
            print(f"Failed to load existing bundle: {e}")
            bundle = manager.create_bundle(args.run_id, args.target_hash)
    else:
        bundle = manager.create_bundle(args.run_id, args.target_hash)

    # If signing requested
    if args.witness_id and args.sign:
        sig = WitnessSignature(
            witness_id=args.witness_id, signature=args.sign, timestamp=time.time()
        )
        if manager.add_signature(args.run_id, sig):
            print(f"Signature from {args.witness_id} added to run {args.run_id}.")
        else:
            print(f"Failed to add signature.")
            sys.exit(1)

    # Verify state
    if args.verify:
        is_valid = bundle.is_verified()
        print(f"Consensus Status: {'VERIFIED' if is_valid else '⏳ PENDING'}")
        print(f"Signatures: {len(bundle.signatures)} / {bundle.threshold}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(bundle.to_dict(), f, indent=2)
        print(f"Witness bundle saved to {args.output}")


if __name__ == "__main__":
    main()
