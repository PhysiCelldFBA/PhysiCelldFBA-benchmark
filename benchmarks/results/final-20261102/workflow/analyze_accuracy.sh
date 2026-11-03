#!/usr/bin/env bash
# Regression check of the streaming analyze_tradeoff.py against the published 20261027 Part A report, then the final Part A analyses.
set -uo pipefail
cd /gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark
module load hdf5 python/3.12.1
source venv/bin/activate
ws=benchmarks/workspaces; ts=benchmarks/results/timestep; v=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark-verify/analyze-regression
rm -rf $v
python benchmarks/performance/analyze_tradeoff.py --campaign proposed-fix $ws/tradeoff-accuracy-fix-20261027 --campaign development $ws/tradeoff-accuracy-dev-20261027 --output $v > /dev/null || { echo "regression run failed"; exit 1; }
python - $ts/tradeoff-accuracy-20261027/tables/runs.csv $v/tables/runs.csv <<'PY'
import csv, sys, math
a, b = ([r for r in csv.DictReader(open(p))] for p in sys.argv[1:])
key = lambda r: (r['build'], r['scenario'], r['ratio'], r['diffusion_dt_minutes'])
A, B = {key(r): r for r in a}, {key(r): r for r in b}
assert A.keys() == B.keys(), 'different runs'
worst = {}
for k in A:
    for col in A[k]:
        if col in ('attempt', 'case_id'): continue
        x, y = A[k][col], B[k].get(col)
        try: d = abs(float(x) - float(y)) / max(1e-300, abs(float(x))) if x not in ('', 'None') else (0 if y in ('', 'None', x) else math.inf)
        except ValueError: d = 0 if x == y else math.inf
        worst[col] = max(worst.get(col, 0), d)
bad = {c: d for c, d in worst.items() if d > 1e-12}
print('regression: %d runs, %d columns; columns differing beyond 1e-12 relative: %s' % (len(A), len(worst), bad or 'none'))
PY
rm -rf $ts/tradeoff-accuracy-d0_01-final-20261102
for d in 0_01 0_001; do
    python benchmarks/performance/analyze_tradeoff.py --campaign pr-c59daa81 $ws/tradeoff-accuracy-fix-d$d-final-20261102 \
        --campaign development-7f2b1d0a $ws/tradeoff-accuracy-dev-d$d-final-20261102 --output $ts/tradeoff-accuracy-d$d-final-20261102 --plots > /dev/null \
        && echo "accuracy d$d done" || echo "accuracy d$d FAILED"
done
