import argparse
import hashlib
import json
import tarfile
from pathlib import Path


def _fmt_ns(x: float | None) -> str:
    if x is None:
        return "NA"
    if x >= 1_000_000:
        return f"{x/1_000_000:.3f} ms"
    if x >= 1_000:
        return f"{x/1_000:.3f} µs"
    return f"{x:.2f} ns"


def _load_json_from_pack(pack_path: Path) -> dict:
    with tarfile.open(pack_path, "r:gz") as tf:
        names = tf.getnames()
        member = None
        for preferred in ("full_telemetry.json", "./full_telemetry.json"):
            if preferred in names:
                member = tf.getmember(preferred)
                break
        if member is None:
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


def _load_host_info_from_pack(pack_path: Path) -> str:
    try:
        with tarfile.open(pack_path, "r:gz") as tf:
            names = tf.getnames()
            member = None
            for preferred in ("host_info.txt", "./host_info.txt"):
                if preferred in names:
                    member = tf.getmember(preferred)
                    break
            if member is None:
                return "Host info missing"
            f = tf.extractfile(member)
            if f is None:
                return "Failed to read host_info.txt"
            return f.read().decode("utf-8").strip()
    except Exception as e:
        return f"Error reading host info: {e}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _data_signature(agg: dict[tuple[str, int], dict]) -> str:
    """
    Hash a canonical view of aggregate results to detect "repacked" duplicates.

    This intentionally ignores telemetry metadata. Two runs can have different pack SHA256
    yet identical aggregate measurements if a pack was duplicated and metadata edited.
    """
    h = hashlib.sha256()
    for (path, size) in sorted(agg.keys()):
        r = agg[(path, size)]
        p50 = float(r.get("p50_median", 0.0))
        p50_iqr = float(r.get("p50_iqr", 0.0))
        p99 = float(r.get("p99_median", 0.0))
        h.update(f"{path}\t{size}\t{p50:.9f}\t{p50_iqr:.9f}\t{p99:.9f}\n".encode("utf-8"))
    return h.hexdigest()


def _load_full(path: Path) -> dict:
    if path.suffixes[-2:] == [".tar", ".gz"] or path.suffix == ".tgz":
        return _load_json_from_pack(path)
    return json.loads(path.read_text())


def _telemetry_meta(path: Path) -> dict:
    try:
        data = _load_full(path)
        meta = data.get("metadata", {}) or {}
        return {
            "run_id": meta.get("run_id"),
            "timestamp": meta.get("timestamp"),
            "python": meta.get("python"),
            "platform": meta.get("platform"),
        }
    except Exception:
        return {}


def load_agg(path: Path) -> dict[tuple[str, int], dict]:
    if path.suffixes[-2:] == [".tar", ".gz"] or path.suffix == ".tgz":
        data = _load_json_from_pack(path)
    else:
        data = json.loads(path.read_text())
    return {(r["path"], int(r["size_bytes"])): r for r in data["aggregate"]}


def parse_labeled_inputs(values: list[str]) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for v in values:
        if "=" not in v:
            raise SystemExit(f"expected label=path, got: {v}")
        label, p = v.split("=", 1)
        out.append((label.strip(), Path(p.strip())))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="one or more label=telemetry.json pairs",
    )
    parser.add_argument("--out", default=None, help="output markdown path (optional)")
    parser.add_argument("--size-o1", type=int, default=1024)
    parser.add_argument("--size-on", type=int, default=10_000_000)
    args = parser.parse_args()

    runs = parse_labeled_inputs(args.inputs)
    input_info = []
    sha_to_labels: dict[str, list[str]] = {}
    for label, path in runs:
        sha = _sha256_file(path)
        sha_to_labels.setdefault(sha, []).append(label)
        meta = _telemetry_meta(path)
        input_info.append(
            {
                "label": label,
                "path": str(path),
                "sha256": sha,
                "bytes": path.stat().st_size,
                "is_pack": path.suffixes[-2:] == [".tar", ".gz"] or path.suffix == ".tgz",
                "run_id": meta.get("run_id"),
                "timestamp": meta.get("timestamp"),
                "platform": meta.get("platform"),
                "python": meta.get("python"),
            }
        )
    aggs = {label: load_agg(path) for label, path in runs}
    sig_to_labels: dict[str, list[str]] = {}
    for label, _path in runs:
        sig = _data_signature(aggs[label])
        sig_to_labels.setdefault(sig, []).append(label)

    rows = [
        ("Python noop", args.size_o1),
        ("C noop", args.size_o1),
        ("Null (PyBytes)", args.size_o1),
        ("Acquire buffer (len_bytes)", args.size_o1),
        ("Null (PyBuffer)", args.size_o1),
        ("Copy (PyBytes to_vec)", args.size_on),
        ("Copy (Buffer to_vec)", args.size_on),
        ("Copy (BytesVec arg)", args.size_on),
        ("Copy (Vec<u8> arg)", args.size_on),
        ("Consume (PyBytes)", args.size_on),
    ]

    labels = [label for label, _p in runs]

    md: list[str] = []
    md.append("# Key-point comparison across runs")
    md.append("")
    dup_groups = [labels for labels in sha_to_labels.values() if len(labels) > 1]
    if dup_groups:
        md.append("**WARNING: duplicate inputs detected (byte-for-byte identical).**")
        md.append(
            "Treat duplicated columns as the *same run*; this is not independent replication."
        )
        for g in dup_groups:
            md.append(f"- duplicates: {', '.join(g)}")
        md.append("")
    dup_sig_groups = [labels for labels in sig_to_labels.values() if len(labels) > 1]
    if dup_sig_groups:
        md.append("**WARNING: duplicate measurement content detected (aggregate signature identical).**")
        md.append(
            "This can happen even when pack SHA256 differs (e.g., repackaging). Treat duplicated columns as the *same run*."
        )
        for g in dup_sig_groups:
            md.append(f"- duplicates: {', '.join(g)}")
        md.append("")
    md.append(f"Sizes: `{args.size_o1}` bytes (O(1) paths), `{args.size_on}` bytes (O(N) paths)")
    md.append("")
    header = ["Path", "Size"] + labels
    md.append("| " + " | ".join(header) + " |")
    md.append("|" + "|".join(["---"] * len(header)) + "|")

    for path, size in rows:
        line = [path, str(size)]
        for label in labels:
            r = aggs[label].get((path, size))
            if not r:
                line.append("NA")
                continue
            # Include p50 (median) and p99 (tail)
            p50 = float(r["p50_median"])
            iqr = float(r.get("p50_iqr", 0))
            p99 = float(r.get("p99_median", 0))
            
            cell = f"{_fmt_ns(p50)} (IQR {_fmt_ns(iqr)})<br/>p99: {_fmt_ns(p99)}"
            line.append(cell)
        md.append("| " + " | ".join(line) + " |")

    md.append("")
    md.append("## Host Information")
    md.append("")
    for label, path in runs:
        if path.suffix in (".tgz", ".gz"):
            info = _load_host_info_from_pack(path)
            md.append(f"### {label}")
            md.append("```")
            md.append(info)
            md.append("```")
            md.append("")

    md.append("")
    md.append("## Footgun factor at 10MB")
    md.append("`Copy (Vec<u8> arg)` divided by `Copy (PyBytes to_vec)` (p50 medians).")
    md.append("")
    md.append("| Run | Factor |")
    md.append("|---|---:|")
    for label in labels:
        a = aggs[label].get(("Copy (Vec<u8> arg)", args.size_on))
        b = aggs[label].get(("Copy (PyBytes to_vec)", args.size_on))
        if not a or not b or float(b["p50_median"]) <= 0:
            md.append(f"| {label} | NA |")
            continue
        factor = float(a["p50_median"]) / float(b["p50_median"])
        md.append(f"| {label} | {factor:,.1f}× |")

    md.append("")
    md.append("## Input Integrity")
    md.append("")
    md.append("| Label | Path | Pack SHA256 | Agg sig | Run id | Timestamp | Bytes | Sizes present | Note |")
    md.append("|---|---|---:|---:|---|---:|---:|---|---|")
    for info in input_info:
        label = str(info["label"])
        path = str(info["path"])
        sha = str(info["sha256"])
        sig = _data_signature(aggs[label])
        run_id = info.get("run_id") or ""
        ts = info.get("timestamp")
        ts_s = f"{ts:.3f}" if isinstance(ts, (int, float)) else ""
        nbytes = int(info["bytes"])
        sizes = sorted({size for (_p, size) in aggs[label].keys()})
        sizes_s = ", ".join(str(s) for s in sizes)
        note = ""
        dup = sha_to_labels.get(sha, [])
        if len(dup) > 1:
            note = f"duplicate of {dup[0]}"
        dup_sig = sig_to_labels.get(sig, [])
        if len(dup_sig) > 1 and not note:
            note = f"agg-duplicate of {dup_sig[0]}"
        md.append(
            f"| {label} | {path} | `{sha}` | `{sig}` | `{run_id}` | {ts_s} | {nbytes} | `{sizes_s}` | {note} |"
        )

    out = "\n".join(md) + "\n"
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Wrote: {args.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()
