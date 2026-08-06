#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/out"
pdflatex WarmLogic_AAAI2026.tex
bibtex WarmLogic_AAAI2026
PYTHONPATH=.. python -m scripts.check_bibtex_warnings WarmLogic_AAAI2026.blg
pdflatex WarmLogic_AAAI2026.tex
pdflatex WarmLogic_AAAI2026.tex
echo "PDF generated → WarmLogic_AAAI2026.pdf"
