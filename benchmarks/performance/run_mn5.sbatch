#!/usr/bin/env bash
# One independent single-node simulation, not MPI/distributed-memory scaling.
# Usage (after resolving the study decisions and staging a case):
# sbatch benchmarks/performance/run_mn5.sbatch /absolute/case/bundle /absolute/results
#SBATCH --job-name=dfba-benchmark
#SBATCH --account=bsc08
#SBATCH --qos=gp_bscls
#SBATCH --partition=gpp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=112
#SBATCH --exclusive
#SBATCH --hint=nomultithread
#SBATCH --time=00:30:00
#SBATCH --output=dfba-benchmark-%j.out
#SBATCH --error=dfba-benchmark-%j.err

set -euo pipefail
bundle=$(realpath "${1:?absolute staged case directory required}")
results=${2:?absolute results directory required}
[[ "$results" = /* ]] || { echo 'Results path must be absolute' >&2; exit 2; }
[[ -f "$bundle/manifest.json" ]] || { echo 'Case has not been staged' >&2; exit 2; }

module load python/3.12.1
# Reserve the same whole node for serial and parallel cases to avoid co-tenancy
# and per-CPU memory-allocation confounding. The case XML chooses active threads.
srun --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK}" --cpu-bind=cores \
    python3 "$bundle/tools/run_case.py" "$bundle" --output-root "$results"
