#!/usr/bin/env bash
# Usage: sbatch --output=/absolute/new-log run_growth.sbatch /absolute/campaign /absolute/build-root
# build-root contains unit/{dfba-unit-test,build.json} and cancer/{cancer-core-metabolism,build.json}.
#SBATCH --job-name=dfba-growth-check
#SBATCH --account=bsc08
#SBATCH --partition=gpp
#SBATCH --qos=gp_debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=01:00:00
set -euo pipefail
campaign=${1:?fresh absolute campaign path required}
build_root=${2:?absolute build root required}
repo=$(pwd)
module load hdf5 python/3.12.1
source "$repo/venv/bin/activate"
srun --input=/dev/null python -m unittest discover -s benchmarks/performance -p test_workflow.py -v
srun --input=/dev/null python benchmarks/performance/prepare_growth.py \
    --unit-binary "$build_root/unit/dfba-unit-test" --unit-build "$build_root/unit/build.json" \
    --cancer-binary "$build_root/cancer/cancer-core-metabolism" --cancer-build "$build_root/cancer/build.json" \
    --output "$campaign"
sha256sum --check "$campaign/campaign.sha256"
failed=0
while IFS= read -r bundle; do
    rc=0
    srun --input=/dev/null --ntasks=1 --cpus-per-task=1 --cpu-bind=cores \
        python "$bundle/tools/run_case.py" "$bundle" --output-root "$campaign/runs" || rc=$?
    printf '%s\t%s\n' "$(basename "$bundle")" "$rc" >> "$campaign/logs/collection.tsv"
    if ((rc)); then failed=1; fi
done < "$campaign/launch-order.txt"
exit "$failed"
