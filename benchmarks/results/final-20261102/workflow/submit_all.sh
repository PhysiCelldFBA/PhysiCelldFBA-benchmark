#!/usr/bin/env bash
# Submit every final campaign prepared by build_prepare.sh. Run from the benchmark repository root on a login node.
# Wall limits: Part B from the cost-pilot loop times t(k=1) per model/threads, t(k) <= t(1) * k^-0.6 (the pilot measured
# a steeper drop), x10 at diffusion dt 0.001, x1.5 margin, +5 min start-up per run (iML1515 loads in ~150 s), x3 repeats,
# +10 min, capped at the 48 h QOS limit.
set -euo pipefail
ws=$(realpath benchmarks/workspaces); w=$ws/final-20261102; jobs=$w/submitted-jobs.tsv
[ -e "$jobs" ] && { echo "$jobs exists; already submitted?"; exit 2; }
printf 'job_id\tname\tcampaign\tlist\n' > "$jobs"
sub() {  # name time campaign part [list]
    local c=$3 part=$4 list=${5:-launch-order.txt}
    local id=$(sbatch --parsable --job-name="$1" --time="$2" --output="$c/$part/logs/slurm-%j.out" --error="$c/$part/logs/slurm-%j.err" \
               "$c/tools/run_mn5.sbatch" "$c" 1 "$part" "$list")
    printf '%s\t%s\t%s\t%s\n' "$id" "$1" "$c" "$list" >> "$jobs"
}
sub dfba-final-voxel 00:30:00 $ws/voxel-final-20261102 voxel_sharing
sub dfba-final-mesh 01:00:00 $ws/mesh-final-20261102 voxel_sharing
for d in 0_01 0_001; do
    t=01:00:00; [ $d = 0_001 ] && t=06:00:00
    for v in fix dev; do sub dfba-final-A-$v-d$d $t $ws/tradeoff-accuracy-$v-d$d-final-20261102 timestep; done
    c=$ws/tradeoff-cost-fix-d$d-final-20261102
    for list in $(cd $c/timestep && ls launch-*-p*-q*.txt); do
        read model threads k < <(echo "$list" | sed -E 's/launch-(.+)-p([0-9]+)-q([0-9]+)\.txt/\1 \2 \3/')
        case "$model-$threads" in ecoli_core-1) t1=44;; ecoli_core-56) t1=2;; mcf7_core-1) t1=258;; mcf7_core-56) t1=7;;
                                  iml1515-1) t1=1668;; iml1515-56) t1=33;; *) echo "unknown group $list"; exit 2;; esac
        scale=1; [ $d = 0_001 ] && scale=10
        secs=$(awk -v t=$t1 -v k=$k -v s=$scale 'BEGIN{x=3*(t*s*k^-0.6*1.5+300)+600; if(x>172800)x=172800; printf "%d", x}')
        mins=$(((secs+59)/60)); sub dfba-final-B-${model}-p$threads-q$k-d$d $(printf '%d:%02d:00' $((mins/60)) $((mins%60))) $c timestep "$list"
    done
done
echo "Submitted $(($(wc -l < "$jobs")-1)) jobs; list in $jobs"
