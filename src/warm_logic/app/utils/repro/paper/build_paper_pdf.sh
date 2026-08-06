#!/bin/bash
set -euo pipefail

latexmk -pdf -interaction=batchmode docs/product/theme_paper_latex_skeleton.tex
cp theme_paper_latex_skeleton.pdf out/theme_paper_latex_skeleton.pdf
echo "PDF built at out/theme_paper_latex_skeleton.pdf"
