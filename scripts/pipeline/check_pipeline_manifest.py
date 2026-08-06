#!/usr/bin/env python3
import json
import sys
from pathlib import Path

REQUIRED = {"pipeline_id", "run_id", "ops_evidence_ids"}
OPTIONAL_PATH_FIELDS = {
    "os_trace",
    ("evidence", "provenance"),
}
OPTIONAL_BUNDLE_FIELDS = {
    "bundle_hash",
    ("evidence", "bundle_hash"),
}
EVIDENCE_MAP_FIELD = "evidence_map"


def _exists_if_present(data: dict, key):
    if isinstance(key, tuple):
        root, child = key
        if root in data and isinstance(data[root], dict) and child in data[root]:
            path = Path(str(data[root][child]))
            return path.exists(), path
        return True, None
    if key in data:
        path = Path(str(data[key]))
        return path.exists(), path
    return True, None


def main() -> int:
    manifest_path = Path("out/ml_runs") / "pipeline_manifest.json"
    if not manifest_path.exists():
        print(f"Pipeline manifest not found at {manifest_path}", file=sys.stderr)
        return 1

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = REQUIRED - set(data)
    if missing:
        print(f"Missing required fields: {missing}", file=sys.stderr)
        return 1

    if not data["ops_evidence_ids"]:
        print("ops_evidence_ids must contain at least one evidence id", file=sys.stderr)
        return 1
    if any(not str(eid).strip() for eid in data["ops_evidence_ids"]):
        print("ops_evidence_ids contains blank entries", file=sys.stderr)
        return 1

    # Semantic v0: referenced paths must resolve if present.
    for key in OPTIONAL_PATH_FIELDS:
        ok, path = _exists_if_present(data, key)
        if not ok and path:
            print(f"Referenced path missing: {path}", file=sys.stderr)
            return 1

    # Bundle hash should be present in both top-level and evidence block when provided.
    bundle_hashes = set()
    for key in OPTIONAL_BUNDLE_FIELDS:
        if isinstance(key, tuple):
            root, child = key
            if root in data and isinstance(data[root], dict) and child in data[root]:
                bundle_hashes.add(str(data[root][child]))
        elif key in data:
            bundle_hashes.add(str(data[key]))
    if len(bundle_hashes) > 1:
        print(f"Bundle hash mismatch between fields: {bundle_hashes}", file=sys.stderr)
        return 1

    # Resolve ops_evidence_ids against evidence_map if provided.
    # evidence_map must resolve ops_evidence_ids; checksum-only is not allowed.
    if EVIDENCE_MAP_FIELD not in data:
        print("evidence_map is required to resolve ops_evidence_ids", file=sys.stderr)
        return 1
    if not isinstance(data[EVIDENCE_MAP_FIELD], dict):
        print(
            "evidence_map must be an object mapping evidence ids to paths",
            file=sys.stderr,
        )
        return 1
    evidence_map = data[EVIDENCE_MAP_FIELD]
    for evid in data["ops_evidence_ids"]:
        if evid not in evidence_map:
            print(
                f"ops_evidence_id '{evid}' not found in evidence_map", file=sys.stderr
            )
            return 1
        path = Path(str(evidence_map[evid]))
        if not path.exists():
            print(f"evidence_map path missing for '{evid}': {path}", file=sys.stderr)
            return 1
        # If JSON, ensure it parses.
        if path.suffix in {".json", ".jsonl"}:
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover
                print(
                    f"Failed to parse JSON evidence for '{evid}' at {path}: {exc}",
                    file=sys.stderr,
                )
                return 1
        if path.suffix in {".yaml", ".yml"}:
            # Light YAML presence check without importing pyyaml.
            if not path.read_text(encoding="utf-8").strip():
                print(f"Empty YAML evidence for '{evid}' at {path}", file=sys.stderr)
                return 1

    print(f"Pipeline manifest {manifest_path} passes contract guard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
