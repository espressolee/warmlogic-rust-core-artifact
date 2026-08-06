#!/usr/bin/env bash
set -euo pipefail

# Publish finalized PDFs to releases/ as SSOT with dated names and latest symlinks.
# Usage:
#   scripts/papers/publish_release.sh --venue ethics_it --date YYYYMMDD

VENUE=""
DATE="$(date +%Y%m%d)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venue) VENUE="$2"; shift 2;;
    --date) DATE="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 --venue <slug> [--date YYYYMMDD]"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$VENUE" ]]; then
  echo "--venue is required (e.g., ethics_it, facct)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Source PDFs (built earlier)
P1_SRC="$ROOT/docs/papers/ai_ethics/2025_beyond_the_ubermensch/submission/Paper1_BeyondTheUbermensch.pdf"
P2_SRC="$ROOT/docs/papers/ai_ethics/2026_moral_finality_measurement_kit/submission/Paper2_MFMK.pdf"
P3_SRC="$ROOT/docs/papers/ai_ethics/2026_case_anatomy_internal_ethics/submission/Paper3_CaseAnatomy.pdf"
P4_SRC="$ROOT/docs/papers/ai_ethics/2026_intervention_design_reopenability/submission/Paper4_InterventionDesign.pdf"
P5_SRC="$ROOT/docs/papers/ai_ethics/2026_stress_test_reopenability/submission/Paper5_StressTest_Reopenability.pdf"
P6_SRC="$ROOT/docs/papers/ai_ethics/2026_adversarial_closure/submission/Paper6_Adversarial_Closure.pdf"
PHD_SRC="$ROOT/docs/papers/ai_ethics/phd/PhD_Combined.pdf"
# Optional bundles (e.g., OS architecture bundle)
OS_BUNDLE_SRC="$ROOT/docs/papers/reflective_os/2025_warmlogic_os_v1/out/Paper_WarmLogic_OS_v1_bundle.zip"
# OS/Pipeline paper PDFs (optional publish)
OS_PAPER_SRC="$ROOT/docs/papers/reflective_os/2025_warmlogic_os_v1/Paper_WarmLogic_OS_v1.pdf"
# Prefer out/ if exists
PIPELINE_PAPER_SRC_OUT="$ROOT/docs/papers/safety_pipeline/2025_ct_safe_pipeline_v1/out/Paper_CT_Safe_Pipeline_v1.pdf"
PIPELINE_PAPER_SRC_ROOT="$ROOT/docs/papers/safety_pipeline/2025_ct_safe_pipeline_v1/Paper_CT_Safe_Pipeline_v1.pdf"
# CT-Safe MDP paper & bundle (optional publish)
CTSAFE_PAPER_SRC_OUT="$ROOT/docs/papers/reflective_os/2025_reflectiveos_ct_safe_mdp_v1/out/Paper_ReflectiveOS_CT_Safe_MDP_v1.pdf"
CTSAFE_PAPER_SRC_ROOT="$ROOT/docs/papers/reflective_os/2025_reflectiveos_ct_safe_mdp_v1/Paper_ReflectiveOS_CT_Safe_MDP_v1.pdf"
CTSAFE_BUNDLE_SRC="$ROOT/docs/papers/reflective_os/2025_reflectiveos_ct_safe_mdp_v1/out/Paper_ReflectiveOS_CT_Safe_MDP_v1_bundle.zip"
# Theme PDFs (optional publish)
THEME_OUT_BASE="$ROOT/docs/papers/themes"
THEME_PDFS=(
  "$THEME_OUT_BASE/2025_theme1/out/2025_theme1.pdf:Theme1_v1"
  "$THEME_OUT_BASE/2025_theme2/out/2025_theme2.pdf:Theme2_v1"
  "$THEME_OUT_BASE/2025_theme3/out/2025_theme3.pdf:Theme3_v1"
  "$THEME_OUT_BASE/2025_theme4/out/2025_theme4.pdf:Theme4_v1"
  "$THEME_OUT_BASE/2025_theme5/out/2025_theme5.pdf:Theme5_v1"
)
# Vol1 main dataset paper (optional publish)
VOL1_MAIN_PDF_DOCS="$ROOT/docs/papers/WarmLogic_Vol1_v1.0/submission/paper/warmlogic_main.pdf"
VOL1_MAIN_PDF_TOP="$ROOT/submission/paper/warmlogic_main.pdf"
# Chapter X Logical Map (standalone PDF)
LOGICAL_MAP_PDF="$ROOT/docs/papers/ai_ethics/phd/out/ChapterX_Logical_Map.pdf"
LOGICAL_MAP_PNG="$ROOT/docs/papers/ai_ethics/phd/out/ChapterX_Logical_Map.png"

DEST_PAPERS="$ROOT/docs/papers/releases/papers"
DEST_PHD="$ROOT/docs/papers/releases/phd"
DEST_BUNDLES="$ROOT/docs/papers/releases/bundles"
mkdir -p "$DEST_PAPERS" "$DEST_PHD" "$DEST_BUNDLES"

publish() {
  local src="$1" name="$2"
  [[ -f "$src" ]] || { echo "[publish] missing: $src" >&2; return 1; }
  local dest="$DEST_PAPERS/${name}_${VENUE}_${DATE}.pdf"
  cp -f "$src" "$dest"
  ln -sfn "$(basename "$dest")" "$DEST_PAPERS/${name}_latest.pdf"
  # Venue-specific latest symlink (e.g., P5_latest_facct.pdf, P5_latest_ethics_it.pdf)
  ln -sfn "$(basename "$dest")" "$DEST_PAPERS/${name}_latest_${VENUE}.pdf"
  echo "[publish] -> $(realpath "$dest")"
}

publish "$P1_SRC" "P1"
publish "$P2_SRC" "P2"
publish "$P3_SRC" "P3"
publish "$P4_SRC" "P4"
publish "$P5_SRC" "P5"
publish "$P6_SRC" "P6"

# PhD combined
if [[ -f "$PHD_SRC" ]]; then
  PHD_DEST="$DEST_PHD/PhD_Combined_${DATE}.pdf"
  cp -f "$PHD_SRC" "$PHD_DEST"
  ln -sfn "$(basename "$PHD_DEST")" "$DEST_PHD/PhD_Combined_latest.pdf"
  echo "[publish] -> $(realpath "$PHD_DEST")"
else
  echo "[publish] missing: $PHD_SRC" >&2
fi

echo "[publish] Done. SSOT in releases/."

# Optional: publish OS bundle if present
if [[ -f "$OS_BUNDLE_SRC" ]]; then
  OS_DEST="$DEST_BUNDLES/OS_WarmLogic_v1_${DATE}.zip"
  cp -f "$OS_BUNDLE_SRC" "$OS_DEST"
  # Additional aliases per request
  ln -sfn "$(basename "$OS_DEST")" "$DEST_BUNDLES/OS_WarmLogic_v1_latest.zip"
  ln -sfn "$(basename "$OS_DEST")" "$DEST_BUNDLES/OS_v1_${DATE}.zip"
  ln -sfn "$(basename "$OS_DEST")" "$DEST_BUNDLES/OS_latest.zip"
  echo "[publish] -> $(realpath "$OS_DEST")"
fi

# Optional: publish OS/Pipeline PDFs with aliases
if [[ -f "$OS_PAPER_SRC" ]]; then
  OS_PDF_DEST="$DEST_PAPERS/OS_v1_${DATE}.pdf"
  cp -f "$OS_PAPER_SRC" "$OS_PDF_DEST"
  ln -sfn "$(basename "$OS_PDF_DEST")" "$DEST_PAPERS/OS_latest.pdf"
  echo "[publish] -> $(realpath "$OS_PDF_DEST")"
fi

PIPE_SRC=""
if [[ -f "$PIPELINE_PAPER_SRC_OUT" ]]; then
  PIPE_SRC="$PIPELINE_PAPER_SRC_OUT"
elif [[ -f "$PIPELINE_PAPER_SRC_ROOT" ]]; then
  PIPE_SRC="$PIPELINE_PAPER_SRC_ROOT"
fi
if [[ -n "$PIPE_SRC" ]]; then
  PIPE_DEST="$DEST_PAPERS/Pipeline_v1_${DATE}.pdf"
  cp -f "$PIPE_SRC" "$PIPE_DEST"
  ln -sfn "$(basename "$PIPE_DEST")" "$DEST_PAPERS/Pipeline_latest.pdf"
  echo "[publish] -> $(realpath "$PIPE_DEST")"
fi

# CT-Safe MDP PDF
CT_PDF_SRC=""
if [[ -f "$CTSAFE_PAPER_SRC_OUT" ]]; then
  CT_PDF_SRC="$CTSAFE_PAPER_SRC_OUT"
elif [[ -f "$CTSAFE_PAPER_SRC_ROOT" ]]; then
  CT_PDF_SRC="$CTSAFE_PAPER_SRC_ROOT"
fi
if [[ -n "$CT_PDF_SRC" ]]; then
  CT_PDF_DEST="$DEST_PAPERS/CTSafeMDP_v1_${DATE}.pdf"
  cp -f "$CT_PDF_SRC" "$CT_PDF_DEST"
  ln -sfn "$(basename "$CT_PDF_DEST")" "$DEST_PAPERS/CTSafeMDP_latest.pdf"
  echo "[publish] -> $(realpath "$CT_PDF_DEST")"
fi

# CT-Safe MDP bundle
if [[ -f "$CTSAFE_BUNDLE_SRC" ]]; then
  CT_BUNDLE_DEST="$DEST_BUNDLES/CTSafeMDP_v1_${DATE}.zip"
  cp -f "$CTSAFE_BUNDLE_SRC" "$CT_BUNDLE_DEST"
  ln -sfn "$(basename "$CT_BUNDLE_DEST")" "$DEST_BUNDLES/CTSafeMDP_latest.zip"
  echo "[publish] -> $(realpath "$CT_BUNDLE_DEST")"
fi

# Theme PDFs
for entry in "${THEME_PDFS[@]}"; do
  src="${entry%%:*}"; name="${entry##*:}"
  if [[ -f "$src" ]]; then
    dest="$DEST_PAPERS/${name}_${DATE}.pdf"
    cp -f "$src" "$dest"
    ln -sfn "$(basename "$dest")" "$DEST_PAPERS/${name}_latest.pdf"
    echo "[publish] -> $(realpath "$dest")"
  fi
done

# Vol1 main dataset paper
V1_SRC=""
if [[ -f "$VOL1_MAIN_PDF_DOCS" ]]; then
  V1_SRC="$VOL1_MAIN_PDF_DOCS"
elif [[ -f "$VOL1_MAIN_PDF_TOP" ]]; then
  V1_SRC="$VOL1_MAIN_PDF_TOP"
fi
if [[ -n "$V1_SRC" ]]; then
  V1_DEST="$DEST_PAPERS/Vol1Main_v1_${DATE}.pdf"
  cp -f "$V1_SRC" "$V1_DEST"
  ln -sfn "$(basename "$V1_DEST")" "$DEST_PAPERS/Vol1Main_latest.pdf"
  echo "[publish] -> $(realpath "$V1_DEST")"
fi

# Publish Chapter X Logical Map if present
if [[ -f "$LOGICAL_MAP_PDF" ]]; then
  MAP_DEST="$DEST_PAPERS/ChapterXLogicalMap_v1_${DATE}.pdf"
  cp -f "$LOGICAL_MAP_PDF" "$MAP_DEST"
  ln -sfn "$(basename "$MAP_DEST")" "$DEST_PAPERS/ChapterXLogicalMap_latest.pdf"
  echo "[publish] -> $(realpath "$MAP_DEST")"
fi
if [[ -f "$LOGICAL_MAP_PNG" ]]; then
  MAP_PNG_DEST="$DEST_PAPERS/ChapterXLogicalMap_v1_${DATE}.png"
  cp -f "$LOGICAL_MAP_PNG" "$MAP_PNG_DEST"
  ln -sfn "$(basename "$MAP_PNG_DEST")" "$DEST_PAPERS/ChapterXLogicalMap_latest.png"
  echo "[publish] -> $(realpath "$MAP_PNG_DEST")"
fi
