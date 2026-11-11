#!/usr/bin/env bash
# Build the supplement PDF from SUPPLEMENTARY.md (vector figures from figures/*.pdf). Run from any directory.
set -euo pipefail
cd "$(dirname "$0")"
module load pandoc/3.2 texlive/20260813 >/dev/null 2>&1 || true
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
sed -E 's#\(figures/(FigS[0-9]+)\.png\)#(figures/\1.pdf)#' SUPPLEMENTARY.md > "$tmp/supplement.md"
cat > "$tmp/header.tex" <<'EOF'
\usepackage{etoolbox}
\AtBeginEnvironment{longtable}{\scriptsize}
\AtBeginEnvironment{Shaded}{\scriptsize}
\usepackage{caption}
\captionsetup{font=small,labelformat=empty}
\setlength{\emergencystretch}{3em}
EOF
pandoc "$tmp/supplement.md" --from markdown --pdf-engine=xelatex --resource-path=. \
  -V geometry:margin=2cm -V papersize=a4 -V mainfont="DejaVu Sans" -V sansfont="DejaVu Sans" \
  -V monofont="Nimbus Mono PS" -V fontsize=10pt -V colorlinks=true -V linkcolor=blue \
  --lua-filter=tables.lua -H "$tmp/header.tex" -o PhysiCelldFBA_benchmark_supplement.pdf
echo "wrote $(pwd)/PhysiCelldFBA_benchmark_supplement.pdf"
