#!/usr/bin/env python3
"""Prepare fresh serial growth-condition controls; never submit or run them."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
from common import digest, read_json, write_json, config_metadata, source_path
from design import plan_cases
from inputs import materialize
from prepare import stage

HERE=Path(__file__).resolve().parent
from common import REPO, SOURCE as ROOT


def growth_cases(study, population=16):
    profiles=read_json(HERE/'growth_profiles.json')
    base=plan_cases(study,'timestep')[0]
    cases=[]
    def add(name,dt,n=1,fixed=False,variant='dfba'):
        profile=profiles[name]
        case=copy.deepcopy(base)
        case.update(phase='growth_validation',model=profile['model'],template=profile['template'],
                    medium_profile=name,cells_requested=n,threads=1,variant=variant,
                    layout='single' if n==1 else 'lattice',fixed_volume=fixed,
                    fields=config_metadata(source_path(profile['template']))['fields'],
                    diffusion_dt_minutes=.01,intracellular_dt_minutes=dt,
                    output_policy='diagnostic_endpoints',status='ready',open_decisions=[],
                    interpretation='serial_medium_validation_not_performance_measurement',
                    validation_record='Candidate-medium pilot: retain all failures, check geometry, growth, solver status and substrates before accepting the profile.')
        case['case_id']=f'growth-{name}-{variant}-n{n}-fixed{int(fixed)}-dt{dt}'.replace('.','_')
        cases.append(case)
    for name in ('ecoli_colony_fed','iml_fed','mcf7_native','mcf7_oxygen2_gradient','mcf7_uniform_fed'):
        for dt in (.01,.1,1): add(name,dt)
    add('iml_batch',.01)
    for name in ('ecoli_colony_fed','iml_fed','mcf7_uniform_fed'):
        for dt in (.01,1): add(name,dt,population,True)
    add('mcf7_native',.01,variant='pfba')
    return cases


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('unit-binary','unit-build','cancer-binary','cancer-build','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--duration',type=float,default=10)
    p.add_argument('--population',type=int,default=16)
    a=p.parse_args()
    if a.duration<10 or a.population<2: raise ValueError('Use at least 10 minutes and two population-control cells')
    if subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True).strip():
        raise ValueError('Commit preparation sources before staging')
    study=read_json(HERE/'study.json'); cases=growth_cases(study,a.population)
    builds={'ecoli_core':(a.unit_binary,a.unit_build),'iml1515':(a.unit_binary,a.unit_build),
            'mcf7_core':(a.cancer_binary,a.cancer_build)}
    for binary,record in builds.values():
        build=read_json(record)
        if digest(binary)!=build['binary_sha256']: raise ValueError('Binary checksum mismatch')
        for name,expected in build['benchmark_harness'].items():
            if digest(HERE/name)!=expected: raise ValueError('Rebuild after harness changes')
    out=a.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','bundles','runs','logs'): (out/name).mkdir()
    write_json(out/'campaign.json',dict(preparation_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        purpose='serial_growth_condition_validation',duration_minutes=a.duration,cases=len(cases),study=study,
        profiles=read_json(HERE/'growth_profiles.json'),population=a.population))
    bundles=[]
    for case in cases:
        inputs=out/'inputs'/case['case_id']; materialize(case,study,inputs,a.duration)
        path=out/(case['case_id']+'.json'); write_json(path,case)
        binary,build=builds[case['model']]; bundle=out/'bundles'/case['case_id']
        stage(argparse.Namespace(case=path,inputs=inputs,binary=binary,build=build,output=bundle))
        path.unlink(); bundles.append(bundle)
    (out/'launch-order.txt').write_text(''.join(str(b)+'\n' for b in bundles))
    pinned=[out/'campaign.json',out/'launch-order.txt']+[b/'manifest.json' for b in bundles]
    (out/'campaign.sha256').write_text(''.join(f'{digest(p)}  {p}\n' for p in pinned))
    print(f'Prepared {len(cases)} serial controls; no jobs submitted.')


if __name__=='__main__': main()
