#!/usr/bin/env bash
# One manuscript-figure simulation, as shipped except optionally the thread count. Usage: sbatch run.sbatch PROJECT CONFIG THREADS|shipped NAME
#SBATCH --account=bsc08
#SBATCH --partition=gpp
#SBATCH --qos=gp_bscls
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=112
#SBATCH --exclusive
#SBATCH --hint=nomultithread
set -euo pipefail
p=$1; config=$2; threads=$3; name=$4
w=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark/benchmarks/workspaces/apps-20261109; b=$w/build/$p; r=$w/runs/$name
[ -e $r ] && { echo "$r exists"; exit 2; }; mkdir -p $r
exe=$(grep -o '^PROGRAM_NAME := .*' $b/Makefile | cut -d' ' -f3)
cp $b/$exe $r/; cp -r $b/config $r/config
if [ "$threads" != shipped ]; then sed -i "s|<omp_num_threads>[0-9]*</omp_num_threads>|<omp_num_threads>$threads</omp_num_threads>|" $r/$config; fi
export OMP_PROC_BIND=spread OMP_PLACES=cores OPENBLAS_NUM_THREADS=1 OMP_DYNAMIC=FALSE
{ echo "project $p"; echo "config $config"; echo "threads_setting $(grep -o '<omp_num_threads>[0-9]*' $r/$config | cut -d'>' -f2)"; echo "binary_sha256 $(sha256sum $r/$exe | cut -c1-64)"
  echo "config_sha256 $(sha256sum $r/$config | cut -c1-64)"; echo "shipped_config_sha256 $(sha256sum $b/$config | cut -c1-64)"
  echo "slurm_job $SLURM_JOB_ID"; echo "host $(hostname)"; echo "start $(date -Is)"; } > $r/run-info.txt
lscpu > $r/lscpu.txt
cd $r; rc=0
/usr/bin/time -v -o $r/time.txt ./$exe $config > $r/stdout.log 2> $r/stderr.log || rc=$?
echo "end $(date -Is)" >> $r/run-info.txt; echo "exit $rc" >> $r/run-info.txt
exit $rc
