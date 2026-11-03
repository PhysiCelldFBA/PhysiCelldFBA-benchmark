#!/usr/bin/env bash
# Analyze every final campaign (PhysiCelldFBA PR commit c59daa81). Writes new report folders only. Run in a compute allocation.
set -uo pipefail
cd /gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark
module load hdf5 python/3.12.1
source venv/bin/activate
ws=benchmarks/workspaces; vs=benchmarks/results/voxel_sharing; ts=benchmarks/results/timestep; gc=benchmarks/results/growth_conditions
step() { echo "=== $1"; shift; "$@" || echo "!!! step failed (exit $?)"; }
step voxel python benchmarks/voxel_sharing/analyze.py --campaign $ws/voxel-final-20261102 --output $vs/voxel-final-20261102 --plots
step mesh python benchmarks/voxel_sharing/analyze.py --campaign $ws/mesh-final-20261102 --output $vs/mesh-final-20261102 --plots
step mesh-summary python benchmarks/voxel_sharing/summarize_mesh.py --report $vs/mesh-final-20261102
step voxel-vs-20261027 python benchmarks/voxel_sharing/compare_builds.py --before $vs/voxel-20261027 $vs/mesh-20261027 \
     --after $vs/voxel-final-20261102 $vs/mesh-final-20261102 --labels a2519f06-pr19 c59daa81-final --output $vs/final-vs-20261027 --plots
for d in 0_01 0_001; do
    step accuracy-d$d python benchmarks/performance/analyze_tradeoff.py --campaign pr-c59daa81 $ws/tradeoff-accuracy-fix-d$d-final-20261102 \
         --campaign development-7f2b1d0a $ws/tradeoff-accuracy-dev-d$d-final-20261102 --output $ts/tradeoff-accuracy-d$d-final-20261102 --plots
    step cost-d$d python benchmarks/performance/analyze_cost.py --campaign $ws/tradeoff-cost-fix-d$d-final-20261102 --output $ts/tradeoff-cost-d$d-final-20261102 --plots
done
step growth python benchmarks/performance/analyze_growth.py $ws/growth-final-20261102/runs --output $gc/growth-final-20261102
python -c 'import sys, matplotlib, numpy, json; print(json.dumps(dict(python=sys.version, matplotlib=matplotlib.__version__, numpy=numpy.__version__)))' > $ws/final-20261102/analysis_environment.json
echo "=== done"
