#!/usr/bin/env bash
# Run inside a compute allocation after jobs 48112700 (voxel) and 48112701 (mesh) finish.
set -euo pipefail
cd /gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA
module load hdf5 python/3.12.1
source venv/bin/activate
res=benchmarks/results/voxel_sharing
python benchmarks/voxel_sharing/analyze.py --campaign benchmarks/workspaces/voxel-20261027 --output $res/voxel-20261027 --plots
python benchmarks/voxel_sharing/analyze.py --campaign benchmarks/workspaces/mesh-20261027 --output $res/mesh-20261027 --plots
python benchmarks/voxel_sharing/summarize_mesh.py --report $res/mesh-20261027
python benchmarks/voxel_sharing/compare_builds.py \
  --before $res/voxel-20261026 $res/mesh-20261026 \
  --after $res/voxel-20261027 $res/mesh-20261027 \
  --labels pre-fix post-fix --output $res/before-after-20261027 --plots
python -c 'import sys, matplotlib, numpy, json; json.dump(dict(python=sys.version, matplotlib=matplotlib.__version__, numpy=numpy.__version__), open(sys.argv[1], "w"), indent=2)' $res/before-after-20261027/analysis_environment.json
