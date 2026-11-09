#!/usr/bin/env bash
# Analyze the pfba and scaling campaigns (PhysiCelldFBA c59daa81). Writes new report folders only.
set -uo pipefail
cd /gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark
module load hdf5 python/3.12.1
source venv/bin/activate
ws=benchmarks/workspaces; r=benchmarks/results
python benchmarks/performance/analyze_pfba.py --campaign $ws/pfba-final-20261104 --output $r/pfba/pfba-final-20261104 --plots
echo "=== pfba exit $?"
python benchmarks/performance/analyze_scaling.py --campaign $ws/scaling-final-20261104 --output $r/performance/scaling-final-20261104 --plots
echo "=== scaling exit $?"
python -c 'import sys, matplotlib, numpy, scipy, json; print(json.dumps(dict(python=sys.version, matplotlib=matplotlib.__version__, numpy=numpy.__version__, scipy=scipy.__version__)))' > $ws/studies-20261104/analysis_environment.json
