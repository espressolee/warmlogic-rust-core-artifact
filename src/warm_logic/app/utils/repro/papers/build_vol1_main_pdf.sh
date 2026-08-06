#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Preferred path inside docs (if exists), else top-level submission/paper
DOCS_DIR="$ROOT/docs/papers/WarmLogic_Vol1_v1.0/submission/paper"
TOP_DIR="$ROOT/submission/paper"

BUILD_DIR=""
if [[ -d "$DOCS_DIR" ]]; then
  BUILD_DIR="$DOCS_DIR"
elif [[ -d "$TOP_DIR" ]]; then
  BUILD_DIR="$TOP_DIR"
else
  echo "[build-vol1] No known Vol1 main paper directory found; skipping." >&2
  exit 0
fi

TEX="$BUILD_DIR/warmlogic_main.tex"
PDF="$BUILD_DIR/warmlogic_main.pdf"

if [[ ! -f "$TEX" ]]; then
  echo "[build-vol1] $TEX not found; skipping." >&2
  exit 0
fi

if ! command -v latexmk >/dev/null 2>&1; then
  echo "[build-vol1] latexmk not found; please install TeX tools (skip)." >&2
  exit 0
fi

echo "[build-vol1] Building $PDF"
# Prefer XeLaTeX for Unicode (Korean) support; fallback to LuaLaTeX; else pdflatex.
ENGINE_ARGS="-pdf"
if command -v xelatex >/dev/null 2>&1; then
  ENGINE_ARGS="-xelatex"
elif command -v lualatex >/dev/null 2>&1; then
  ENGINE_ARGS="-lualatex"
fi
(cd "$BUILD_DIR" && latexmk ${ENGINE_ARGS} -f -g -quiet "$(basename "$TEX")")
echo "[build-vol1] Wrote $PDF"
