#!/usr/bin/env bash
# Stock builds (no benchmark hooks) of the six manuscript sample projects from the pinned submodule. Run in a compute allocation.
set -euo pipefail
repo=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark; w=$repo/benchmarks/workspaces/apps-20261109
ext=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA/addons/dFBA/ext
commit=$(git -C $repo/PhysiCelldFBA rev-parse HEAD); [ "${commit:0:8}" = c59daa81 ] || { echo "submodule not at c59daa81"; exit 2; }
for x in dfba_unit_test:dfba_unit_test ecoli_acetic_switch:ecoli-acetic-switch-sample bacterial_colony:bacterial-colony cancer_core_metabolism:cancer-core-metabolism crossfeeding:crossfeeding metabolic_driven_motility:metabolic_driven_motility; do
    p=${x%%:*}; target=${x#*:}; d=$w/build/$p
    [ -e $d ] && { echo "$d exists"; exit 2; }; mkdir -p $d
    git -C $repo/PhysiCelldFBA archive $commit | tar -C $d -x
    [ -e $d/addons/dFBA/ext ] && mv $d/addons/dFBA/ext $d/ext-placeholder
    ln -s $ext $d/addons/dFBA/ext
    ( cd $d && make $target > staging.log 2>&1 && make -j16 > build.log 2>&1 ) || { echo "$p: build failed"; exit 1; }
    exe=$(grep -o '^PROGRAM_NAME := .*' $d/Makefile | cut -d' ' -f3)
    echo "$p $exe $(sha256sum $d/$exe | cut -c1-64) $commit" | tee -a $w/builds.tsv
done
g++ --version | head -n 1 > $w/compiler.txt; grep -m1 -o 'g++ .* -c' $w/build/dfba_unit_test/build.log | sed 's/ -c$//' >> $w/compiler.txt
