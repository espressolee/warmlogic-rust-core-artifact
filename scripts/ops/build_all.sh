#!/usr/bin/env bash
set -euo pipefail

# Global build orchestrator for papers (v1)
# Builds all PDFs, then refreshes releases exports and checksums per ARTIFACT_REGISTRY.yaml.

ROOT="$(cd "$(dirname "$0")" && pwd)"
REG="$ROOT/ARTIFACT_REGISTRY.yaml"
CHECKSUMS="$ROOT/releases/CHECKSUMS_SHA256.txt"

build_paper() {
  local path="$1"
  echo "[build-all] Building $path"
  bash "$path"
}

refresh_checksums() {
  echo "[build-all] Refreshing checksums under releases/"
  find "$ROOT/releases" -type f ! -path "*CHECKSUMS_SHA256.txt" -print0 \
    | sort -z \
    | xargs -0 sha256sum > "$CHECKSUMS"
}

generate_manifest() {
  echo "[build-all] Generating releases/RELEASE_MANIFEST.json"
  python - <<'PY'
import hashlib, json, os, pathlib, datetime, yaml
root = pathlib.Path(__file__).resolve().parent
manifest_path = root / "releases" / "RELEASE_MANIFEST.json"
reg = yaml.safe_load(open(root / "ARTIFACT_REGISTRY.yaml"))
artifacts = []
for art in reg.get("artifacts", []):
    exp = art.get("export", {})
    path = exp.get("export_path") if exp.get("enabled") else art.get("source_path")
    if not path or art.get("artifact_id") in {"RELEASE-META-ZENODO", "P5-REVIEWER-PACKET-FACCT-ZIP", "P5-REVIEWER-PACKET-EIT-ZIP"}:
        continue
    artifacts.append({"id": art["artifact_id"], "path": path})

checksums = {}
for art in artifacts:
    path = (root / art["path"]).resolve()
    if not path.exists():
        checksums[art["id"]] = None
        continue
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    checksums[art["id"]] = h.hexdigest()

manifest = {
    "version": "v1.0",
    "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "artifacts": artifacts,
    "checksums": checksums,
}
manifest_path.write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
PY
}

echo "[build-all] START"

# Build all paper PDFs (ai_ethics v1)
build_paper "$ROOT/docs/papers/ai_ethics/2025_beyond_the_ubermensch/submission/build_pdf.sh"
build_paper "$ROOT/docs/papers/ai_ethics/2026_moral_finality_measurement_kit/submission/build_pdf.sh"
build_paper "$ROOT/docs/papers/ai_ethics/2026_case_anatomy_internal_ethics/submission/build_pdf.sh"
build_paper "$ROOT/docs/papers/ai_ethics/2026_intervention_design_reopenability/submission/build_pdf.sh"
build_paper "$ROOT/docs/papers/ai_ethics/2026_stress_test_reopenability/submission/build_pdf.sh"
build_paper "$ROOT/docs/papers/ai_ethics/2026_adversarial_closure/submission/build_pdf.sh"

# Export artifacts per registry (for now: copy enabled exports)
echo "[build-all] Exporting artifacts (registry-enabled)"
python - <<'PY'
import yaml, shutil, os, hashlib, sys

root = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(root, "ARTIFACT_REGISTRY.yaml"), "r") as f:
    reg = yaml.safe_load(f)

def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

exported = []
for art in reg.get("artifacts", []):
    exp = art.get("export", {})
    if not exp or not exp.get("enabled"):
        continue
    src = os.path.join(root, art["source_path"])
    dst = os.path.join(root, exp["export_path"])
    if not os.path.exists(src):
        print(f"[WARN] source missing: {src}", file=sys.stderr)
        continue
    ensure_dir(dst)
    shutil.copy2(src, dst)
    exported.append(dst)
    print(f"[export] {src} -> {dst}")

print(f"[export] total exported: {len(exported)}")
PY

# Refresh checksums
refresh_checksums
generate_manifest

echo "[build-all] DONE"
