#!/usr/bin/env bash
# Submit the pfba and scaling campaigns, one job per pinned case list. Run from the benchmark repository root on a login node.
# Scaling wall limits: dFBA loop time per 1000 cells measured in the cost study (k = 1, dt 0.01): 1 thread for p < 56, 56 threads
# for p >= 56, scaled by cells/1000, x1.5 margin, + iML1515 start-up 0.15 s/cell, + 5 min per run; x3 repeats + 10 min;
# variants without metabolism get 30 min per job. Capped at the 48 h QOS limit.
set -euo pipefail
ws=$(realpath benchmarks/workspaces); w=$ws/studies-20261104; jobs=$w/submitted-jobs.tsv
[ -e "$jobs" ] && { echo "$jobs exists; already submitted?"; exit 2; }
printf 'job_id\tname\tcampaign\tlist\n' > "$jobs"
sub() {  # name minutes campaign list
    local h=$(printf '%d:%02d:00' $(($2/60)) $(($2%60)))
    local id=$(sbatch --parsable --job-name="$1" --time="$h" --output="$3/timestep/logs/slurm-%j.out" --error="$3/timestep/logs/slurm-%j.err" \
               "$3/tools/run_mn5.sbatch" "$3" 1 timestep "$4")
    printf '%s\t%s\t%s\t%s\n' "$id" "$1" "$3" "$4" >> "$jobs"
}
c=$ws/pfba-final-20261104
sub dfba-pfba-single 60 $c launch-single.txt
for l in $(cd $c/timestep && ls launch-application-*.txt); do sub dfba-pfba-${l#launch-} 360 $c $l; done
c=$ws/scaling-final-20261104
for l in $(cd $c/timestep && ls launch-*.txt | grep -v launch-order); do
    read model variant cells threads < <(echo "$l" | sed -E 's/launch-(ecoli_core|mcf7_core|iml1515)-(dfba|dfba_disabled|upstream_physicell)-n([0-9]+)-p([0-9]+)-f[0-9]+\.txt/\1 \2 \3 \4/')
    if [ "$variant" != dfba ]; then mins=30; else
        case "$model" in ecoli_core) t1=46; t56=2;; mcf7_core) t1=257; t56=7;; iml1515) t1=1674; t56=44;; *) echo "unknown $l"; exit 2;; esac
        init=0; [ $model = iml1515 ] && init=$(( cells * 15 / 100 ))
        mins=$(awk -v a=$t1 -v b=$t56 -v n=$cells -v p=$threads -v i=$init 'BEGIN{t=(p<56?a:b)*n/1000*1.5+i+300; x=(3*t+600)/60; if(x>2880)x=2880; printf "%d", x+1}')
    fi
    sub dfba-scal-${l#launch-} $mins $c $l
done
echo "Submitted $(($(wc -l < "$jobs")-1)) jobs; list in $jobs"
