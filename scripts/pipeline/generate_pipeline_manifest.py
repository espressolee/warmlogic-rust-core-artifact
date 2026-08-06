#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path


def make_manifest(args):
    data = {
        "pipeline_id": args.pipeline_id,
        "run_id": args.run_id,
        "autonomy_level": args.autonomy_level,
        "os_trace": args.os_trace,
        "ops_evidence_ids": args.ops_evidence_ids,
        "bundle_hash": args.bundle_hash,
        "evidence": {
            "bundle_hash": args.bundle_hash,
            "provenance": args.provenance,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Generate a pipeline_manifest_v1.json conforming to Theme 2 schemas."
    )
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--autonomy-level", required=True)
    parser.add_argument("--os-trace", default="logs/evidence/govdec.jsonl")
    parser.add_argument("--ops-evidence-ids", nargs="+", required=True)
    parser.add_argument("--bundle-hash", required=True)
    parser.add_argument(
        "--provenance",
        default="docs/papers/reflective_os_ct_safe_mdp_v1/out/provenance.README",
    )
    parser.add_argument("--output", default="out/ml_runs/pipeline_manifest.json")
    args = parser.parse_args()

    manifest = make_manifest(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote pipeline manifest to {output_path}")


if __name__ == "__main__":
    main()
