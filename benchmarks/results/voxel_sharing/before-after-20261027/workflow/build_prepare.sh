#!/usr/bin/env bash
# Run inside a compute allocation. Builds, prepares the two campaigns and runs preflights; submits nothing.
set -euo pipefail
cd /gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA
module load hdf5 python/3.12.1
source venv/bin/activate
base="$PWD/benchmarks/workspaces/racefix-20261027-build"
python -m unittest discover -s benchmarks/performance -p test_workflow.py -v
python -m unittest discover -s benchmarks/voxel_sharing -p test_campaign.py -v
bash benchmarks/performance/build.sh "$PWD" "$base/unit" dfba_unit_test 16
python "$base/record_build.py" "$base/unit" dfba-unit-test .local-workspace/mn5-20261026/prepared/provenance/unit.json
python benchmarks/voxel_sharing/prepare.py --binary "$base/unit/dfba-unit-test" --build "$base/unit/build.json" --output benchmarks/workspaces/voxel-20261027 > "$base/staging-voxel.log"
python benchmarks/voxel_sharing/prepare.py --protocol benchmarks/voxel_sharing/mesh_protocol.json --binary "$base/unit/dfba-unit-test" --build "$base/unit/build.json" --output benchmarks/workspaces/mesh-20261027 > "$base/staging-mesh.log"
python "$base/preflight.py" benchmarks/workspaces/voxel-20261027 benchmarks/workspaces/mesh-20261027 > "$base/preflight.log"
echo 'Build, preparation and preflights passed.'
