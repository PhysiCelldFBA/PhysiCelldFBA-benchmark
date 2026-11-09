#!/usr/bin/env bash
# PhysiCelldFBA's own dfba_unit_test suite on the benchmarked commit c59daa81 (stock build, no benchmark hooks):
# voxel sharing (n1/n4/n8/mixed: non-negativity, equal draw), update order (12 cells, 5 orders, 1 and 4 threads)
# and dx-dt (voxel size and time step, including the intracellular-dt ratio series). Run in a compute allocation.
set -uo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
build=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark/benchmarks/workspaces/apps-20261109/build/dfba_unit_test
module load hdf5 python/3.12.1
export PYTHON=/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark-verify/venv-dxdt/bin/python JOBS=16
d=$here/tree; [ -e $d ] && { echo "$d exists"; exit 2; }
cp -r $build $d
echo "source_commit c59daa81bc13c459b9421b3fb5dbb7b6200b3b8b" > $here/provenance.txt
sha256sum $d/dfba-unit-test >> $here/provenance.txt; $PYTHON -c 'import cobra, numpy, scipy; print("cobra", cobra.__version__, "numpy", numpy.__version__, "scipy", scipy.__version__)' >> $here/provenance.txt
echo "host $(hostname) cpus $(nproc)" >> $here/provenance.txt
( cd $d && bash scripts/run_voxel_sharing_test.sh ./dfba-unit-test > $here/voxel_sharing_and_update_order.log 2>&1 ); echo "voxel-sharing + update-order exit $?" | tee -a $here/summary.txt
( cd $d && bash scripts/run_dxdt_test.sh ./dfba-unit-test > $here/dxdt.log 2>&1 ); echo "dx-dt exit $?" | tee -a $here/summary.txt
for f in voxel_sharing_and_update_order dxdt; do echo "$f: $(grep -c '^PASS\|  ok' $here/$f.log) pass lines, $(grep -c '^FAIL\|FAIL$' $here/$f.log) fail lines" | tee -a $here/summary.txt; done
