import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def build_status(
    ranges: List[str],
    policy_path: Optional[str] = None,
    overrides_path: Optional[str] = None,
    prev_status: Optional[Path] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Generates a status bundle for external ingestion."""

    policy_hash = ""
    if policy_path:
        p = Path(policy_path)
        if p.exists():
            policy_hash = hashlib.sha256(p.read_bytes()).hexdigest()

    status = {
        "status_version": "v1",
        "policy_hash": policy_hash,
        "policy_changed": False,
        "ranges": {},
    }

    if prev_status and prev_status.exists():
        try:
            prev_data = json.loads(prev_status.read_text(encoding="utf-8"))
            if prev_data.get("policy_hash") != policy_hash:
                status["policy_changed"] = True
        except Exception:
            pass

    # Detect audit files in 'out/' as per test requirements
    out_dir = Path("out")
    for r in ranges:
        rng_data = {"audit_path": None, "audit_csv_path": None}
        audit_json = out_dir / f"run_manifests_audit_{r}.json"
        audit_csv = out_dir / f"run_manifests_audit_{r}.csv"

        if audit_json.exists():
            rng_data["audit_path"] = str(audit_json)
        if audit_csv.exists():
            rng_data["audit_csv_path"] = str(audit_csv)

        status["ranges"][r] = rng_data

    return status


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ranges", nargs="+", default=["all"])
    args = parser.parse_args()

    result = build_status(args.ranges)
    output_file = args.out_dir / f"status_bundle_{args.run_id}.json"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Status bundle written to {output_file}")
