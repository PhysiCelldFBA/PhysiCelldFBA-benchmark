#!/usr/bin/env bash
# Verify the standalone benchmark repository against the original builds and campaigns. Submits nothing.
set -uo pipefail
repo=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark
old=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA
work=$(cd -- "$(dirname -- "$0")" && pwd)
export DFBA_EXT=$old/addons/dFBA/ext
module load hdf5 python/3.12.1
source $old/venv/bin/activate
cd $repo
echo "== repository $(git rev-parse --short HEAD), submodule $(git -C PhysiCelldFBA rev-parse --short HEAD), clean: $(git status --porcelain | wc -l) changes"

echo "== unit tests"
python -m unittest discover -s benchmarks/performance -p test_workflow.py 2>&1 | tail -n 3
python -m unittest discover -s benchmarks/voxel_sharing -p test_campaign.py 2>&1 | tail -n 3

echo "== dry-run preparation (no jobs) with the post-fix binary; compare with the original campaigns"
for c in voxel mesh; do
    proto=benchmarks/voxel_sharing/protocol.json; [ $c = mesh ] && proto=benchmarks/voxel_sharing/mesh_protocol.json
    python benchmarks/voxel_sharing/prepare.py --protocol $proto \
        --binary $old/benchmarks/workspaces/racefix-20261027-build/unit/dfba-unit-test \
        --build $old/benchmarks/workspaces/racefix-20261027-build/unit/build.json \
        --output $work/dryrun-$c > $work/dryrun-$c.log 2>&1 || { echo "$c: preparation FAILED"; tail -n 5 $work/dryrun-$c.log; continue; }
    tail -n 1 $work/dryrun-$c.log
    python - $work/dryrun-$c $old/benchmarks/workspaces/$c-20261027 <<'EOF'
import json, sys
from pathlib import Path
new, ref = map(Path, sys.argv[1:])
a, b = (json.loads((p/'campaign.json').read_text()) for p in (new, ref))
print('  input_sources identical:', a['input_sources'] == b['input_sources'], '| protocol identical:', a['protocol_sha256'] == b['protocol_sha256'])
print('  cases.jsonl identical:', (new/'voxel_sharing/cases.jsonl').read_text() == (ref/'voxel_sharing/cases.jsonl').read_text())
keys = lambda p: {m.parent.name: json.loads(m.read_text())['comparison_key'] for m in (p/'voxel_sharing/bundles').glob('*/manifest.json')}
ka, kb = keys(new), keys(ref)
print('  bundle comparison keys identical:', ka == kb, f'({len(ka)} bundles)')
EOF
done

echo "== builds from public commits + physicelldfba-hooks.patch"
git -C PhysiCelldFBA worktree add -q --detach $work/src-b0d810b4 b0d810b4
cp -r benchmarks/performance $work/harness-8ae6a1d7
git -C $old show 8ae6a1d7:benchmarks/performance/runtime.h > $work/harness-8ae6a1d7/runtime.h
build() {  # name source harness project expected original_build_dir
    bash $3/build.sh $2 $work/build-$1 $4 16 > $work/build-$1.log 2>&1 || { echo "$1: build FAILED"; tail -n 5 $work/build-$1.log; return; }
    exe=$work/build-$1/dfba-unit-test; [ $4 = cancer_core_metabolism ] && exe=$work/build-$1/cancer-core-metabolism
    got=$(sha256sum $exe | cut -d' ' -f1)
    if [ "$got" = "$5" ]; then echo "$1: binary IDENTICAL ($got)"; else
        echo "$1: binary differs (got $got, expected $5); comparing compiled sources with $6"
        diff -rq --exclude='*.o' --exclude='*.d' --exclude='*.log' --exclude=output --exclude=benchmarks $work/build-$1 $6 2>&1 | grep -v 'Only in' | grep -E '\.(cpp|h|hpp|c)|Makefile' | head
        echo "  (end of differing compiled sources)"
    fi
}
build A-postfix-unit  PhysiCelldFBA          benchmarks/performance       dfba_unit_test         c74353427dee5e54bdc8d362d9076174f5c560851f48aa5407892aaa40ac359f $old/benchmarks/workspaces/racefix-20261027-build/unit
build B-prefix-unit   $work/src-b0d810b4     benchmarks/performance       dfba_unit_test         29bc0c4af38076edde9ce48f784022659ab0b8351d7538580bf34073c98882cb $old/benchmarks/workspaces/mesh-followup-20261026-build/unit
build C-prefix-voxel  $work/src-b0d810b4     $work/harness-8ae6a1d7       dfba_unit_test         2990326295d1bd5df798fbc5cb504618f41453192e4936b317dacfec3dea56de $old/.local-workspace/mn5-20261026/builds/unit
build D-prefix-cancer $work/src-b0d810b4     benchmarks/performance       cancer_core_metabolism e2034f57e36e1e1d48e8517cd363a30292100eeeb61c95b483d3ec315ddf37fa $old/benchmarks/workspaces/mesh-followup-20261026-build/cancer
git -C PhysiCelldFBA worktree remove --force $work/src-b0d810b4
echo "== repository still clean: $(git status --porcelain | wc -l) changes"
