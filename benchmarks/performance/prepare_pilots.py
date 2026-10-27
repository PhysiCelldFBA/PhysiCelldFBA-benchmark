#!/usr/bin/env python3
"""Stage serial timestep/refinement pilots in a new campaign; never submit jobs."""
import argparse
import json
from pathlib import Path
import random
import shutil
import subprocess
from common import digest, read_json, write_json
from design import plan_cases
from inputs import materialize
from prepare import stage

HERE=Path(__file__).resolve().parent
from common import REPO, SOURCE as ROOT


def pilot_cases(study):
    cases=plan_cases(study,'timestep')+plan_cases(study,'refinement')
    for case in cases:
        case.update(case_id='pilot-'+case['case_id'],status='ready',open_decisions=[],
                    interpretation='duration_and_numerical_sensitivity_pilot',
                    validation_record='Serial single-cell pilot with explicit timestep ratios/refinement and bundled model validation; duration is provisional. Retain all diagnostic flags; no ground-truth yield or accuracy threshold assumed.')
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('unit-binary','unit-build','cancer-binary','cancer-build','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--duration',type=float,default=10,help='Provisional simulated minutes for every pilot (default 10)')
    args=parser.parse_args()
    if args.duration<10: raise ValueError('Use at least 10 minutes to sample the largest interval repeatedly')
    if args.output.exists(): raise ValueError('Use a new output folder')
    if subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'],text=True).strip():
        raise ValueError('Commit preparation sources before staging')
    study=read_json(HERE/'study.json'); cases=pilot_cases(study)
    builds={'ecoli_core':(args.unit_binary,args.unit_build),'mcf7_core':(args.cancer_binary,args.cancer_build)}
    for binary,record in builds.values():
        if digest(binary)!=read_json(record)['binary_sha256']: raise ValueError('Binary checksum mismatch')
    out=args.output.resolve(); out.mkdir(parents=True)
    part=out/'timestep'
    for folder in ('inputs','bundles','runs','tables','plots','logs'): (part/folder).mkdir(parents=True)
    (out/'tools').mkdir(); shutil.copy2(HERE.parent/'voxel_sharing/run_mn5.sbatch',out/'tools/run_mn5.sbatch')
    write_json(out/'study.json',study)
    write_json(out/'campaign.json',dict(preparation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        duration_minutes=args.duration,cases=len(cases),active_part='timestep',status='pilot_only',
        decisions_pending=['Final duration after inspecting dynamics','Accuracy criterion from pilot results','Verified mass-conversion yield'],
        launch_order_seed=20261028))
    bundles=[]
    with (part/'cases.jsonl').open('x') as stream:
        for case in cases:
            stream.write(json.dumps(case,sort_keys=True)+'\n')
            inputs=part/'inputs'/case['case_id']; materialize(case,study,inputs,args.duration)
            record=part/(case['case_id']+'.json'); write_json(record,case)
            binary,build=builds[case['model']]
            bundle=part/'bundles'/case['case_id']
            stage(argparse.Namespace(case=record,inputs=inputs,binary=binary,build=build,output=bundle))
            record.unlink(); bundles.append(bundle)
    random.Random(20261028).shuffle(bundles)
    (part/'launch-order.txt').write_text(''.join(str(p)+'\n' for p in bundles))
    pinned=[out/'campaign.json',out/'study.json',out/'tools/run_mn5.sbatch',part/'cases.jsonl',part/'launch-order.txt']+[b/'manifest.json' for b in bundles]
    (out/'campaign.sha256').write_text(''.join(f'{digest(p)}  {p}\n' for p in pinned))
    print(f'Prepared {len(cases)} serial pilots at {out}; no jobs submitted.')


if __name__=='__main__': main()
