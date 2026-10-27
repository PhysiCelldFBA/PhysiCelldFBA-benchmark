#!/usr/bin/env bash
# Independent check: the dfba_unit_test voxel-sharing + update-order test (PR #19) on two isolated trees.
#   postfix/  tracked source at HEAD (includes PR #19)
#   prefix/   the same tree with core/PhysiCell_cell_container.cpp and BioFVM/BioFVM_basic_agent.cpp
#             restored from b0d810b4 (before PR #19); negative control, expected to fail the update-order check
# Stock project main and build (no benchmark hooks). Run inside a compute allocation with >= 4 cores.
set -uo pipefail
repo=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA
here=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$repo"
module load hdf5 python/3.12.1
source venv/bin/activate
commit=$(git rev-parse HEAD)
for variant in postfix prefix; do
    dest="$here/$variant"
    [ -e "$dest" ] && { echo "$dest exists; use a new folder"; exit 2; }
    mkdir "$dest"
    git archive HEAD | tar -C "$dest" -x --exclude=benchmarks
    if [ "$variant" = prefix ]; then
        git show b0d810b4:core/PhysiCell_cell_container.cpp > "$dest/core/PhysiCell_cell_container.cpp"
        git show b0d810b4:BioFVM/BioFVM_basic_agent.cpp > "$dest/BioFVM/BioFVM_basic_agent.cpp"
    fi
    [ -e "$dest/addons/dFBA/ext" ] && mv "$dest/addons/dFBA/ext" "$dest/ext-placeholder"
    ln -s "$repo/addons/dFBA/ext" "$dest/addons/dFBA/ext"
    ( cd "$dest" && make dfba_unit_test > staging.log 2>&1 && make -j16 > build.log 2>&1 ) || { echo "$variant: build failed"; continue; }
    {
        echo "source_commit $commit"
        echo "variant $variant"
        sha256sum "$dest/dfba-unit-test" "$dest/core/PhysiCell_cell_container.cpp" "$dest/BioFVM/BioFVM_basic_agent.cpp"
        g++ --version | head -n 1
        echo "host $(hostname) cpus $(nproc)"
    } > "$dest/provenance.txt"
    ( cd "$dest" && PYTHON=python bash scripts/run_voxel_sharing_test.sh ./dfba-unit-test > test.log 2>&1 )
    rc=$?
    echo "$variant exit $rc" | tee -a "$here/summary.txt"
    tail -n 15 "$dest/test.log" >> "$here/summary.txt"
done
