#!/usr/bin/env python3
"""Prepare a reproducible eight-cell campaign. Never execute or submit simulations."""
import argparse
import copy
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'performance'))
from common import REPO, SOURCE as ROOT, config_metadata, digest, read_json, source_path, write_json
from design import plan_cases
from inputs import materialize
from prepare import stage


def cases_for_protocol(protocol, study):
    template=source_path(protocol['template'])
    metadata=config_metadata(template)
    if int(ET.parse(template).findtext('user_parameters/number_of_cells')) != protocol['cells']:
        raise ValueError('Protocol population differs from original unit test')
    steps={m['effective_minutes'] for m in metadata['intracellular'].values()}
    if len(steps)!=1: raise ValueError('Expected one intracellular timestep')
    study=dict(study)
    study['simulation_seed']=protocol['simulation_seed']
    study['voxel']={**study['voxel'],'cells':[protocol['cells']],
                   'threads':protocol['threads'],'order_seeds':protocol['order_seeds'],
                   'repeats':protocol['repeats'],'template':protocol['template']}
    cases=plan_cases(study,'voxel')
    for c in cases:
        c.update(initial_position=protocol['initial_position'],intracellular_dt_minutes=next(iter(steps)),
                 status='ready',open_decisions=[],
                 validation_record='Existing n8 unit-test settings, explicitly fixed position/population, once-per-run order permutation; diagnostic findings are retained, not assumed absent.',
                 interpretation='shared_voxel_diagnostic')
    if 'meshes' in protocol:
        expanded=[]
        for mesh in protocol['meshes']:
            for original in cases:
                c=copy.deepcopy(original)
                c.pop('initial_position')
                c.update(layout='explicit',initial_positions=protocol['initial_positions'],
                         mesh_id=mesh['id'],voxel_size_um=mesh['voxel_size_um'],
                         expected_max_occupancy=mesh['expected_max_occupancy'],
                         case_id=mesh['id']+'-'+c['case_id'],
                         interpretation='mesh_occupancy_diagnostic',
                         validation_record='Fixed distinct coordinates across meshes; predicted occupancy checked during materialization and observed occupancy recorded at runtime. Matched serial reference per mesh; scheduler/exchange code identified by the build record; flagged findings retained.')
                expanded.append(c)
        cases=expanded
    return cases,metadata['max_time_minutes']


def prepare(args):
    if args.output.exists(): raise ValueError('Use a new campaign folder')
    protocol=read_json(args.protocol)
    study=read_json(HERE.parent/'performance/study.json')
    cases,duration=cases_for_protocol(protocol,study)
    build=read_json(args.build)
    if digest(args.binary)!=build['binary_sha256']: raise ValueError('Binary checksum mismatch')
    for name, expected in build['benchmark_harness'].items():
        if digest(HERE.parent/'performance'/name)!=expected: raise ValueError(f'Harness changed: {name}')
    # These are experimental inputs; pin their identity independently of binaries.
    identities={name:digest(source_path(name)) for name in (protocol['template'],study['models']['ecoli_core']['path'])}
    revision=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
    if subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'],text=True).strip():
        raise ValueError('Commit preparation sources before staging a campaign')
    out=args.output.resolve(); out.mkdir(parents=True)
    for part in ('timestep','voxel_sharing','pfba','performance'):
        for folder in ('inputs','bundles','runs','tables','plots','logs'):
            (out/part/folder).mkdir(parents=True)
    (out/'tools').mkdir()
    shutil.copy2(HERE/'run_mn5.sbatch',out/'tools/run_mn5.sbatch')
    shutil.copy2(args.build,out/'build.json')
    write_json(out/'protocol.json',protocol)
    write_json(out/'campaign.json',dict(schema_version=1,preparation_commit=revision,
        simulation_commit=build['source_commit'],protocol_sha256=digest(args.protocol),
        input_sources=identities,duration_minutes=duration,cases=len(cases),
        active_part='voxel_sharing',other_parts='planned; not submitted',
        expected_threads=protocol['threads'],order_seeds=protocol['order_seeds'],repeats=protocol['repeats']))
    part=out/'voxel_sharing'
    bundles=[]
    with (part/'cases.jsonl').open('x') as stream:
        for case in cases:
            stream.write(json.dumps(case,sort_keys=True)+'\n')
            inputs=part/'inputs'/case['case_id']
            materialize(case,study,inputs,duration)
            casefile=inputs/'case.json'; write_json(casefile,case)
            # Keep bookkeeping outside the staged scientific inputs.
            record=part/(case['case_id']+'.json'); casefile.rename(record)
            bundle=part/'bundles'/case['case_id']
            stage(argparse.Namespace(case=record,inputs=inputs,binary=args.binary,build=args.build,output=bundle))
            record.unlink()
            bundles.append(bundle)
    random.Random(protocol['launch_order_seed']).shuffle(bundles)
    (part/'launch-order.txt').write_text(''.join(str(p)+'\n' for p in bundles))
    pinned=[out/'campaign.json',out/'protocol.json',out/'build.json',out/'tools/run_mn5.sbatch',part/'cases.jsonl',part/'launch-order.txt']+[p/'manifest.json' for p in bundles]
    (out/'campaign.sha256').write_text(''.join(f'{digest(p)}  {p}\n' for p in pinned))
    print(f'Prepared {len(cases)} cases at {out}; duration {duration} min. No jobs submitted.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=HERE/'protocol.json')
    for name in ('binary','build','output'): parser.add_argument('--'+name,type=Path,required=True)
    prepare(parser.parse_args())

if __name__=='__main__': main()
