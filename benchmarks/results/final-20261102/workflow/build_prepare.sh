#!/usr/bin/env bash
# Final runs: build the PR commit (c59daa81, submodule) and development 7f2b1d0a (unfixed, Part A comparison only),
# record builds, prepare every campaign and run a few preflight cases. Submits nothing. Run in a compute allocation.
set -euo pipefail
cd /gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark
module load hdf5 python/3.12.1
source venv/bin/activate
export DFBA_EXT=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA/addons/dFBA/ext
w=$PWD/benchmarks/workspaces/final-20261102; ws=$PWD/benchmarks/workspaces
unit_t=benchmarks/results/voxel_sharing/voxel-20261027/build.json
cancer_t=benchmarks/results/timestep/pilot-20261026/data/pilot-timestep-mcf7_core-dfba-n1-p1-f23-q1-h1-oNone-r1/manifest.json
[ "$(git -C PhysiCelldFBA rev-parse --short=8 HEAD)" = c59daa81 ] || { echo "submodule not at c59daa81"; exit 2; }
python -m unittest discover -s benchmarks/performance -p test_workflow.py
python -m unittest discover -s benchmarks/voxel_sharing -p test_campaign.py
mkdir -p $w/fix $w/dev
git -C PhysiCelldFBA worktree add -q --detach $w/src-7f2b1d0a 7f2b1d0a
note_fix="PhysiCelldFBA PR fix/intracellular-dt-exchange @ c59daa81 (development 7f2b1d0a + exchange fix) with benchmark hooks; no extra patches."
note_dev="PhysiCelldFBA development @ 7f2b1d0a (exchange defect present) with benchmark hooks; Part A comparison only."
bash benchmarks/performance/build.sh PhysiCelldFBA $w/fix/unit dfba_unit_test 16
bash benchmarks/performance/build.sh PhysiCelldFBA $w/fix/cancer cancer_core_metabolism 16
bash benchmarks/performance/build.sh $w/src-7f2b1d0a $w/dev/unit dfba_unit_test 16
bash benchmarks/performance/build.sh $w/src-7f2b1d0a $w/dev/cancer cancer_core_metabolism 16
for v in fix dev; do n=note_$v
    python benchmarks/performance/record_build.py $w/$v/unit dfba-unit-test --template $unit_t --notes "${!n}"
    python benchmarks/performance/record_build.py $w/$v/cancer cancer-core-metabolism --template $cancer_t --notes "${!n}"
done
git -C PhysiCelldFBA worktree remove --force $w/src-7f2b1d0a
B() { echo --unit-binary $w/$1/unit/dfba-unit-test --unit-build $w/$1/unit/build.json --cancer-binary $w/$1/cancer/cancer-core-metabolism --cancer-build $w/$1/cancer/build.json; }
python benchmarks/voxel_sharing/prepare.py --binary $w/fix/unit/dfba-unit-test --build $w/fix/unit/build.json --output $ws/voxel-final-20261102 | tail -n 1
python benchmarks/voxel_sharing/prepare.py --protocol benchmarks/voxel_sharing/mesh_protocol.json --binary $w/fix/unit/dfba-unit-test --build $w/fix/unit/build.json --output $ws/mesh-final-20261102 | tail -n 1
for dt in 0.01 0.001; do d=${dt/./_}
    for v in fix dev; do l=pr-c59daa81; [ $v = dev ] && l=development-7f2b1d0a
        python benchmarks/performance/prepare_tradeoff.py --stage accuracy --label $l --duration 240 --diffusion-dt $dt $(B $v) --output $ws/tradeoff-accuracy-$v-d$d-final-20261102 | tail -n 1
    done
    python benchmarks/performance/prepare_tradeoff.py --stage cost --label pr-c59daa81 --duration 10 --diffusion-dt $dt $(B fix) --output $ws/tradeoff-cost-fix-d$d-final-20261102 | tail -n 1
done
# Preflight: a few short cases of each kind on the fixed build, outside the campaign runs.
pre() { python $1/tools/run_case.py $1 --output-root $2 > /dev/null 2>&1 || true
        m=$(ls -d $2/$(basename $1)_*/ | head -1); echo "preflight $(basename $1): $(python -c "import json,sys; m=json.load(open(sys.argv[1]+'metrics.json')); t=m.get('telemetry') or {}; print(m['status'], 'threads', t.get('actual_threads'), 'updates', t.get('intracellular_updates'), 'flags', t.get('diagnostic_flags'))" $m)"; }
pre $ws/voxel-final-20261102/voxel_sharing/bundles/voxel-ecoli_core-dfba-n8-p8-f4-q1-h1-o11-r1 $w/preflight
pre $ws/mesh-final-20261102/voxel_sharing/bundles/mesh2-voxel-ecoli_core-dfba-n8-p8-f4-q1-h1-o11-r1 $w/preflight
for d in 0_01 0_001; do
    pre $ws/tradeoff-accuracy-fix-d$d-final-20261102/timestep/bundles/tradeoff_accuracy-A1-ecoli_core-n1-q10-d$d $w/preflight
done
pre $ws/tradeoff-cost-fix-d0_01-final-20261102/timestep/bundles/tradeoff_cost-iml1515-n1000-p56-f23-q100-d0_01-r1 $w/preflight
echo 'Builds, preparation and preflights done.'
