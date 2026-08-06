#!/usr/bin/env bash
set -euo pipefail

# make_submission_bundle.sh
# Packages a paper directory into out/submission/<venue>/<yyyymmdd>_<slug>_bundle.zip
# Default targets Paper 1 (AI Ethics) if --paper-root is omitted.

usage() {
  cat <<'USAGE'
Usage:
  scripts/papers/make_submission_bundle.sh \
    --venue <venue_slug> \
    [--paper-root docs/papers/ai_ethics/2025_beyond_the_ubermensch] \
    [--date YYYYMMDD] [--slug <name>] [--dry-run]

Examples:
  scripts/papers/make_submission_bundle.sh --venue facct
  scripts/papers/make_submission_bundle.sh --venue ethics_it --date 20251230

Notes:
  - Packages: manuscript, figures, bib (master), optional meta/README.
  - Output: out/submission/<venue>/<YYYYMMDD>_<slug>_bundle.zip
USAGE
}

PAPER_ROOT="docs/papers/ai_ethics/2025_beyond_the_ubermensch"
VENUE=""
DATE="$(date +%Y%m%d)"
SLUG=""
DRY_RUN=0
ANON=0
RENDER_FIGS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --paper-root) PAPER_ROOT="$2"; shift 2;;
    --venue) VENUE="$2"; shift 2;;
    --date) DATE="$2"; shift 2;;
    --slug) SLUG="$2"; shift 2;;
    --anonymize) ANON=1; shift;;
    --render-figures) RENDER_FIGS=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$VENUE" ]]; then
  echo "--venue is required" >&2
  usage
  exit 1
fi

if [[ ! -d "$PAPER_ROOT" ]]; then
  echo "Paper root not found: $PAPER_ROOT" >&2
  exit 2
fi

# Derive slug from folder name if not provided
if [[ -z "$SLUG" ]]; then
  SLUG="$(basename "$PAPER_ROOT")"
fi

OUT_DIR="out/submission/${VENUE}"
STAGING_DIR="${OUT_DIR}/${DATE}_${SLUG}"
ZIP_PATH="${OUT_DIR}/${DATE}_${SLUG}_bundle.zip"

echo "[bundle] venue=${VENUE} date=${DATE} slug=${SLUG}"
echo "[bundle] paper_root=${PAPER_ROOT}"
echo "[bundle] staging=${STAGING_DIR}"
echo "[bundle] zip=${ZIP_PATH}"

if [[ $DRY_RUN -eq 1 ]]; then
  exit 0
fi

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR" "$OUT_DIR"

# Copy manuscript
if [[ -f "$PAPER_ROOT/src/paper.md" ]]; then
  mkdir -p "$STAGING_DIR/src"
  if [[ $ANON -eq 1 ]]; then
    python3 scripts/papers/anonymize_md.py "$PAPER_ROOT/src/paper.md" "$STAGING_DIR/src/paper.md"
  else
    cp "$PAPER_ROOT/src/paper.md" "$STAGING_DIR/src/paper.md"
  fi
else
  echo "[warn] manuscript not found: $PAPER_ROOT/src/paper.md" >&2
fi

# Copy figures (if any)
if [[ -d "$PAPER_ROOT/figures" ]]; then
  mkdir -p "$STAGING_DIR/figures"
  if [[ $RENDER_FIGS -eq 1 ]]; then
    # Render all .mmd in-place to .svg under staging
    for mm in "$PAPER_ROOT"/figures/*.mmd; do
      [[ -f "$mm" ]] || continue
      base=$(basename "$mm")
      out="$STAGING_DIR/figures/${base%.mmd}.svg"
      # Ensure target dir exists
      bash scripts/render_mermaid.sh "$mm" "$out" || {
        echo "[warn] figure render failed: $mm" >&2
      }
    done
  fi
  rsync -a --exclude '.*' "$PAPER_ROOT/figures/" "$STAGING_DIR/figures/" || true
fi

# Copy meta and README if present
[[ -f "$PAPER_ROOT/README.md" ]] && cp "$PAPER_ROOT/README.md" "$STAGING_DIR/"
[[ -f "$PAPER_ROOT/meta/changelog.md" ]] && mkdir -p "$STAGING_DIR/meta" && cp "$PAPER_ROOT/meta/changelog.md" "$STAGING_DIR/meta/"

# Copy submission assets (cover letter / reviewer Q&A) if present
if [[ -d "$PAPER_ROOT/submission" && $ANON -eq 0 ]]; then
  mkdir -p "$STAGING_DIR/submission"
  # include common md assets only (avoid uploading portal-specific forms accidentally)
  find "$PAPER_ROOT/submission" -maxdepth 1 -type f -name '*letter*ai*' -o -name '*cover*letter*' -o -name 'reviewer_qna*' -o -name '*ethics_it*.md' -o -name '*ai_and_society*.md' | while read -r f; do
    # guard against empty globs
    [[ -f "$f" ]] && cp "$f" "$STAGING_DIR/submission/"
  done
fi

# Include shared bibliography
mkdir -p "$STAGING_DIR/bib"
cp "docs/papers/_shared/bib/master.bib" "$STAGING_DIR/bib/master.bib"

# Add bundle README with compile hints
cat > "$STAGING_DIR/bundle_README.txt" <<'BREADME'
Bundle contents
- src/paper.md             (manuscript, Markdown + YAML front matter)
- figures/                 (SVG/PNG/PDF and .mmd sources if present)
- bib/master.bib           (shared bibliography; citeproc-friendly)
- README.md, meta/changelog.md (if provided)

Suggested compile (Pandoc >= 2.17)
  pandoc src/paper.md \
    --from markdown+yaml_metadata_block --pdf-engine=xelatex \
    --citeproc --bibliography=bib/master.bib \
    -V geometry:margin=1in -V linkcolor:blue \
    -o paper.pdf

Notes
- Figures are linked via relative paths in the manuscript.
- If mermaid (.mmd) sources are present, render to SVG (e.g., mermaid-cli) before compiling.
BREADME

# Create a simple manifest with file hashes and commit sha
COMMIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
DATE_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TMP_FILES_LIST="$(mktemp)"
trap 'rm -f "$TMP_FILES_LIST"' EXIT

find "$STAGING_DIR" -type f | sort | while read -r f; do
  rel="${f#${STAGING_DIR}/}"
  sha=$(shasum -a 256 "$f" | awk '{print $1}')
  printf '    {"path": "%s", "sha256": "%s"},\n' "$rel" "$sha" >> "$TMP_FILES_LIST"
done

# Remove trailing comma from the last entry if present
if [[ -s "$TMP_FILES_LIST" ]]; then
  # inplace-like: write to a temp then move back
  tmp2="$(mktemp)"; trap 'rm -f "$TMP_FILES_LIST" "$tmp2"' EXIT
  sed '$ s/},$/}/' "$TMP_FILES_LIST" > "$tmp2" && mv "$tmp2" "$TMP_FILES_LIST"
fi

{
  echo '{'
  echo "  \"venue\": \"${VENUE}\","
  echo "  \"date\": \"${DATE}\","
  echo "  \"commit\": \"${COMMIT_SHA}\","
  echo "  \"paper_root\": \"${PAPER_ROOT}\","
  echo "  \"files\": ["
  if [[ -s "$TMP_FILES_LIST" ]]; then cat "$TMP_FILES_LIST"; fi
  echo "  ],"
  echo "  \"generated_at\": \"${DATE_ISO}\""
  echo '}'
} > "$STAGING_DIR/manifest.json"

# Zip it
rm -f "$ZIP_PATH"
(cd "$OUT_DIR" && zip -qr "$(basename "$ZIP_PATH")" "$(basename "$STAGING_DIR")")

echo "[bundle] created: $ZIP_PATH"
