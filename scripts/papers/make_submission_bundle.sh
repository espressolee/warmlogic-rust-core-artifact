#!/usr/bin/env bash
set -euo pipefail

venue=""
paper_root=""
anonymize=0
render_figures=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venue)
      venue="$2"; shift 2;;
    --paper-root)
      paper_root="$2"; shift 2;;
    --anonymize)
      anonymize=1; shift;;
    --render-figures)
      render_figures=1; shift;;
    *)
      echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

[[ -n "$venue" ]] || { echo "--venue required" >&2; exit 2; }
[[ -n "$paper_root" ]] || { echo "--paper-root required" >&2; exit 2; }

slug="$(basename "$paper_root")"
out_dir="out/submission/${venue}"
mkdir -p "$out_dir"

ts="$(date -u +%Y%m%d%H%M%S)"
bundle_path="${out_dir}/${ts}_${slug}_bundle.zip"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

mkdir -p "$work/${slug}/src"
if [[ -f "${paper_root}/src/paper.md" ]]; then
  cp "${paper_root}/src/paper.md" "$work/${slug}/src/paper.md"
else
  cat > "$work/${slug}/src/paper.md" <<'MD'
---
title: Placeholder Submission
authors: ["espressolee"]
abstract: "Auto-generated placeholder paper for CI bundle validation."
---

# Placeholder

See @warm_logic_foundation.
MD
fi

cat > "$work/${slug}/bundle_meta.json" <<JSON
{
  "venue": "${venue}",
  "paper_root": "${paper_root}",
  "slug": "${slug}",
  "anonymized": ${anonymize},
  "render_figures": ${render_figures}
}
JSON

(
  cd "$work"
  zip -qr "$OLDPWD/$bundle_path" "$slug"
)

echo "[BUNDLE] wrote $bundle_path"
