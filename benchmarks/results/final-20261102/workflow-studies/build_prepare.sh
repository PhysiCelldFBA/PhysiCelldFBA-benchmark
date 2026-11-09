#!/usr/bin/env bash
# Build upstream PhysiCell 49d7cc54, prepare the pfba, pfba application pilot and scaling campaigns, run preflights.
# Submits nothing. Run inside a full-node compute allocation (56-thread preflights).
set -euo pipefail
cd /gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark
module load hdf5 python/3.12.1
source venv/bin/activate
ws=$PWD/benchmarks/workspaces; w=$ws/studies-20261104; fb=$ws/final-20261102
[ "$(git -C PhysiCelldFBA rev-parse --short=8 HEAD)" = c59daa81 ] || { echo "submodule not at c59daa81"; exit 2; }
python -m unittest discover -s benchmarks/performance -p test_workflow.py
python -m unittest discover -s benchmarks/voxel_sharing -p test_campaign.py
src=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA
git -C $src worktree add -q --detach $w/src-upstream 49d7cc54
bash benchmarks/performance/build.sh $w/src-upstream $w/upstream template 16
python benchmarks/performance/record_build.py $w/upstream project --template benchmarks/performance/build-templates/upstream.json \
    --notes "Upstream PhysiCell 49d7cc54 (template project) with the core-only benchmark hooks (upstream-hooks.patch); performance baseline."
git -C $src worktree remove --force $w/src-upstream
B="--unit-binary $fb/fix/unit/dfba-unit-test --unit-build $fb/fix/unit/build.json --cancer-binary $fb/fix/cancer/cancer-core-metabolism --cancer-build $fb/fix/cancer/build.json"
python benchmarks/performance/prepare_final_studies.py --stage pfba --label pr-c59daa81 $B --output $ws/pfba-final-20261104
python benchmarks/performance/prepare_final_studies.py --stage pfba --label pr-c59daa81-application-pilot --application-minutes 60 --single-minutes 10 $B --output $ws/pfba-pilot-20261104
python benchmarks/performance/prepare_final_studies.py --stage scaling --label pr-c59daa81 $B --upstream-binary $w/upstream/project --upstream-build $w/upstream/build.json --output $ws/scaling-final-20261104
pre() {  # bundle: run it outside the campaign runs and print the outcome
    python $1/tools/run_case.py $1 --output-root $w/preflight > /dev/null 2>&1 || true
    m=$(ls -d $w/preflight/$(basename $1)_*/ | head -1)
    python -c "import json,sys; m=json.load(open(sys.argv[1]+'metrics.json')); t=m.get('telemetry') or {}; print('preflight', sys.argv[2], m['status'], 'wall', m.get('resource',{}).get('elapsed_seconds'), 's threads', t.get('actual_threads'), 'cells', t.get('initial_cells'), '->', t.get('final_cells'), 'updates', t.get('intracellular_updates'), 'stage-two failures', t.get('stage_two_failures'), 'flags', t.get('diagnostic_flags'))" $m $(basename $1)
}
for b in $ws/pfba-pilot-20261104/timestep/bundles/*application*; do pre $b; done
for b in $ws/pfba-final-20261104/timestep/bundles/pfba-mcf7_core-*-dt0_1; do pre $b; done
s=$ws/scaling-final-20261104/timestep/bundles
for pat in 'main-ecoli_core-upstream_physicell-n100-p1-*-r1*' 'main-mcf7_core-dfba_disabled-n100-p1-*-r1*' 'main-iml1515-dfba-n100-p56-*-r1*' 'main-mcf7_core-upstream_physicell-n1000-p56-*-r1*'; do
    b=$(ls -d $s/$pat 2>/dev/null | head -1); [ -n "$b" ] && pre $b || echo "no bundle for $pat"
done
echo "groups: pfba $(ls $ws/pfba-final-20261104/timestep/launch-*.txt | grep -vc launch-order) scaling $(ls $ws/scaling-final-20261104/timestep/launch-*.txt | grep -vc launch-order)"
echo 'Build, preparation and preflights done.'
