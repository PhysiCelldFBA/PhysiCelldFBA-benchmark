"""Run seed 11, repeat 1 at 1 and 8 threads for every mesh of the given campaigns.

Outputs go to <campaign>/preflight/runs, separate from the campaign runs.
Hard checks: completion, thread count, fixed population, observed occupancy, 80 serial updates.
Parallel update counts are recorded, not required.
"""
import json
from pathlib import Path
import subprocess
import sys
root=Path.cwd(); sys.path.insert(0,str(root/'benchmarks/performance'))
from common import read_json,write_json
for campaign in map(Path,sys.argv[1:]):
    checks=[]
    manifests=[read_json(p) for p in (campaign/'voxel_sharing/bundles').glob('*/manifest.json')]
    for mesh in sorted({m['case'].get('mesh_id','original') for m in manifests}):
        for threads in (1,8):
            manifest=next(m for m in manifests if m['case'].get('mesh_id','original')==mesh
                          and m['case']['threads']==threads and m['case']['order_seed']==11 and m['case']['repeat']==1)
            case=manifest['case']; bundle=campaign/'voxel_sharing/bundles'/case['case_id']
            subprocess.run([sys.executable,str(bundle/'tools/run_case.py'),str(bundle),'--output-root',str(campaign/'preflight/runs')],check=False)
            run=next(p.parent for p in (campaign/'preflight/runs').glob('*/manifest.json') if read_json(p)['case']['case_id']==case['case_id'])
            metrics=read_json(run/'metrics.json'); telemetry=metrics.get('telemetry') or {}
            if metrics['status'] not in ('completed','completed_flagged'): raise ValueError(str(metrics))
            if telemetry['actual_threads']!=threads: raise ValueError('Wrong actual threads')
            if telemetry['initial_cells']!=8 or telemetry['final_cells']!=8: raise ValueError('Wrong population')
            if 'expected_max_occupancy' in case and telemetry['max_cells_per_voxel']!=case['expected_max_occupancy']: raise ValueError('Wrong observed occupancy')
            if threads==1 and telemetry['intracellular_updates']!=80: raise ValueError('Unexpected serial update count')
            checks.append(dict(case_id=case['case_id'],run=str(run),status=metrics['status'],occupancy=telemetry['max_cells_per_voxel'],
                               actual_updates=telemetry['intracellular_updates'],min_concentration=telemetry.get('min_concentration'),
                               flags=telemetry['diagnostic_flags']))
    write_json(campaign/'preflight/validation.json',dict(passed=True,checks=checks))
    print(json.dumps(checks,indent=2))
