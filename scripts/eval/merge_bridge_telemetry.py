import argparse
import json
import tarfile
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_from_pack(pack_path: Path) -> dict[str, Any]:
    # Expect a tarball produced by scripts/eval/collect_host_pack.sh containing full_telemetry.json.
    with tarfile.open(pack_path, "r:gz") as tf:
        names = tf.getnames()
        member = None

        # Prefer exact names (avoid macOS AppleDouble `._*` entries).
        for preferred in ("full_telemetry.json", "./full_telemetry.json"):
            if preferred in names:
                member = tf.getmember(preferred)
                break

        if member is None:
            # Fallback: first member ending with full_telemetry.json, ignoring AppleDouble sidecars.
            for name in names:
                base = Path(name).name
                if not name.endswith("full_telemetry.json"):
                    continue
                if base.startswith("._") or "/._" in name:
                    continue
                member = tf.getmember(name)
                break
        if member is None:
            raise ValueError(f"{pack_path} does not contain full_telemetry.json")
        f = tf.extractfile(member)
        if f is None:
            raise ValueError(f"failed to read {member.name} from {pack_path}")
        return json.loads(f.read().decode("utf-8"))


def host_id(meta: dict[str, Any]) -> str:
    py = str(meta.get("python", "")).split("\n")[0]
    plat = str(meta.get("platform", ""))
    cpu = str(meta.get("cpu", ""))
    run_id = str(meta.get("run_id", "")).strip()
    timestamp = str(meta.get("timestamp", "")).strip()

    # NOTE: Multiple independent runs on identical (cpu, platform, python) must not collapse to
    # one "host" column. Prefer a stable run_id when available; otherwise fall back to timestamp.
    suffix = run_id or timestamp
    if suffix:
        return f"{cpu} | {plat} | {py} | {suffix}"
    return f"{cpu} | {plat} | {py}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs",
        nargs="+",
        help="one or more eval_bridge_v3 full_telemetry.json files, or host pack .tgz files",
    )
    parser.add_argument("--out", default="out/bridge_eval/multi_host/combined.json")
    args = parser.parse_args()

    inputs = [Path(p) for p in args.inputs]
    datasets = []
    for p in inputs:
        if p.suffixes[-2:] == [".tar", ".gz"] or p.suffix == ".tgz":
            d = load_from_pack(p)
            datasets.append({"path": f"{p}::full_telemetry.json", "host": host_id(d.get("metadata", {})), "data": d})
        else:
            d = load(p)
            datasets.append({"path": str(p), "host": host_id(d.get("metadata", {})), "data": d})

    # Combine per (path,size): store per-host p50_median and p50_iqr.
    combined: dict[str, Any] = {"hosts": [], "by_key": {}}
    for ds in datasets:
        combined["hosts"].append({"telemetry": ds["path"], "host": ds["host"], "metadata": ds["data"].get("metadata", {})})

        for row in ds["data"].get("aggregate", []):
            key = (row["path"], int(row["size_bytes"]))
            key_str = f"{key[0]}|{key[1]}"
            slot = combined["by_key"].setdefault(
                key_str, {"path": key[0], "size_bytes": key[1], "per_host": []}
            )
            slot["per_host"].append(
                {
                    "host": ds["host"],
                    "p50_median": float(row["p50_median"]),
                    "p50_iqr": float(row["p50_iqr"]),
                    "p99_median": float(row.get("p99_median", 0.0)),
                    "p99_iqr": float(row.get("p99_iqr", 0.0)),
                    "repeats": int(row.get("repeats", 0)),
                }
            )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(combined, indent=2))

    print(f"Wrote: {out_path}")
    print(f"Hosts: {len(combined['hosts'])}")


if __name__ == "__main__":
    main()
