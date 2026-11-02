#!/usr/bin/env bash
# Usage: sbatch --output=/absolute/campaign/voxel_sharing/logs/slurm-%j.out \
#   benchmarks/voxel_sharing/run_mn5.sbatch /absolute/campaign
#SBATCH --job-name=dfba-voxel
#SBATCH --account=bsc08
#SBATCH --partition=gpp
#SBATCH --qos=gp_bscls
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=112
#SBATCH --exclusive
#SBATCH --hint=nomultithread
#SBATCH --time=00:30:00
set -euo pipefail
campaign=$(realpath "${1:?absolute campaign folder required}")
start_index=${2:-1}
part_name=${3:-voxel_sharing}
# Optional fourth argument: a case list in the part folder (a pinned subset such as launch-<group>.txt).
list_name=${4:-launch-order.txt}
case "$part_name" in voxel_sharing|timestep) ;; *) echo 'Unknown campaign part' >&2; exit 2;; esac
[[ "$list_name" =~ ^launch-[A-Za-z0-9_.-]+\.txt$ ]] || { echo 'Case list must be a launch-*.txt file' >&2; exit 2; }
[[ "$start_index" =~ ^[1-9][0-9]*$ ]] || { echo 'Start index must be a positive integer' >&2; exit 2; }
sha256sum --check "$campaign/campaign.sha256"
module load hdf5 python/3.12.1
part="$campaign/$part_name"
grep -q " $part/$list_name\$" "$campaign/campaign.sha256" || { echo 'Case list is not pinned in campaign.sha256' >&2; exit 2; }
(( start_index <= $(wc -l < "$part/$list_name") )) || { echo 'Start index exceeds case count' >&2; exit 2; }
report="$part/logs/collection-${SLURM_JOB_ID}.tsv"
(set -C; printf 'case_id\tcollector_exit\n' > "$report")
failed=0
while IFS= read -r bundle; do
    rc=0
    # srun otherwise forwards this loop's input and can consume the remaining
    # case list. Neither the collector nor simulation requires standard input.
    srun --input=/dev/null --ntasks=1 --cpus-per-task="$SLURM_CPUS_PER_TASK" --cpu-bind=cores \
        python3 "$bundle/tools/run_case.py" "$bundle" --output-root "$part/runs" < /dev/null || rc=$?
    printf '%s\t%s\n' "$(basename "$bundle")" "$rc" >> "$report"
    if (( rc != 0 )); then failed=1; fi
done < <(tail -n +"$start_index" "$part/$list_name")
# A completed but flagged diagnostic returns nonzero too; every case is retained
# and subsequent cases are still run. Inspect metrics.json, not only Slurm state.
exit "$failed"
