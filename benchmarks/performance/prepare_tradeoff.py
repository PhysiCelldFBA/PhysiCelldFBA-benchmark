#!/usr/bin/env python3
"""Prepare a timestep trade-off campaign (TIMESTEP_TRADEOFF.md); never submits or runs simulations.

Stages:
  checks    ratio-1 depletion runs of scenarios A1-A4 and iML1515 single-cell runs at k = 1, 10, 100
  accuracy  scenarios A1-A4 at every ratio, plus a diffusion-dt 0.005 reference of A3
All cases are serial with fixed positions and population; metabolic biomass growth is on.
"""
import argparse
import copy
import json
from pathlib import Path
import random
import shutil
import subprocess
from common import REPO, SOURCE as ROOT, config_metadata, digest, read_json, write_json
from design import plan_cases
from inputs import materialize
from prepare import stage

HERE = Path(__file__).resolve().parent
RATIOS = (1, 2, 5, 10, 20, 50, 100)
DIFFUSION_DT = 0.01
# id: (model, template or medium profile, cells)
SCENARIOS = {
    'A1': ('ecoli_core', None, 1),               # unit-test mass conversion, 1.6 um voxels, 10 mM glucose
    'A2': ('ecoli_core', 'ecoli_colony_fed', 16),  # bacterial-colony medium, 2 um voxels
    'A3': ('mcf7_core', None, 1),                # cancer_core_metabolism single cell, 15 um voxels
    'A4': ('mcf7_core', 'mcf7_uniform_fed', 16),  # cancer fed medium, 15 um voxels
    'I1': ('iml1515', 'iml_fed', 1),             # iML1515 fed medium, check before Part B
}


def case_for(study, base, phase, scenario, ratio, duration, diffusion_dt=DIFFUSION_DT):
    model, profile_id, cells = SCENARIOS[scenario]
    case = copy.deepcopy(base)
    template = (read_json(HERE/'growth_profiles.json')[profile_id]['template'] if profile_id
                else study['models'][model]['template'])
    case.update(phase=phase, scenario=scenario, model=model, template=template, cells_requested=cells, threads=1,
                variant='dfba', layout='single' if cells == 1 else 'lattice', fixed_positions=True,
                fixed_population=True, fixed_volume=False, fields=config_metadata(ROOT/template)['fields'],
                diffusion_dt_minutes=diffusion_dt, intracellular_dt_minutes=diffusion_dt*ratio, ratio=ratio,
                duration_minutes=duration, output_policy='diagnostic_endpoints', status='ready', open_decisions=[],
                interpretation='timestep_tradeoff_accuracy', order_seed=None,
                validation_record='Serial trade-off case: fixed positions/population, biomass growth on; retain every flag.')
    case.pop('medium_profile', None)
    if profile_id: case['medium_profile'] = profile_id
    case['case_id'] = f'{phase}-{scenario}-{model}-n{cells}-q{ratio}-d{diffusion_dt}'.replace('.', '_')
    return case


def cases_for_stage(study, name, duration):
    base = plan_cases(study, 'timestep')[0]
    if name == 'checks':
        cases = [case_for(study, base, 'tradeoff_check', s, 1, duration) for s in ('A1', 'A2', 'A3', 'A4')]
        cases += [case_for(study, base, 'tradeoff_check', 'I1', k, min(duration, 60)) for k in (1, 10, 100)]
    else:
        cases = [case_for(study, base, 'tradeoff_accuracy', s, k, duration) for s in ('A1', 'A2', 'A3', 'A4') for k in RATIOS]
        cases.append(case_for(study, base, 'tradeoff_accuracy', 'A3', 1, duration, diffusion_dt=DIFFUSION_DT/2))
    return cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=('checks', 'accuracy'), required=True)
    for name in ('unit-binary', 'unit-build', 'cancer-binary', 'cancer-build', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--duration', type=float, required=True, help='Simulated minutes (iML1515 checks use at most 60)')
    p.add_argument('--label', required=True, help='Build label recorded in campaign.json, e.g. proposed-fix or development')
    a = p.parse_args()
    if a.duration < 10: raise ValueError('Use at least 10 simulated minutes')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).strip():
        raise ValueError('Commit preparation sources before staging')
    study = read_json(HERE/'study.json'); cases = cases_for_stage(study, a.stage, a.duration)
    builds = {'ecoli_core': (a.unit_binary, a.unit_build), 'iml1515': (a.unit_binary, a.unit_build),
              'mcf7_core': (a.cancer_binary, a.cancer_build)}
    for binary, record in builds.values():
        build = read_json(record)
        if digest(binary) != build['binary_sha256']: raise ValueError('Binary checksum mismatch')
        for name, expected in build['benchmark_harness'].items():
            if digest(HERE/name) != expected: raise ValueError(f'Rebuild after harness changes: {name}')
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    part = out/'timestep'
    for folder in ('inputs', 'bundles', 'runs', 'tables', 'plots', 'logs'): (part/folder).mkdir(parents=True)
    (out/'tools').mkdir(); shutil.copy2(HERE.parent/'voxel_sharing/run_mn5.sbatch', out/'tools/run_mn5.sbatch')
    write_json(out/'study.json', study)
    write_json(out/'campaign.json', dict(preparation_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        purpose='timestep_tradeoff_'+a.stage, protocol='benchmarks/performance/TIMESTEP_TRADEOFF.md', build_label=a.label,
        duration_minutes=a.duration, cases=len(cases), scenarios={k: list(v) for k, v in SCENARIOS.items()},
        builds={m: read_json(r)['binary_sha256'] for m, (_, r) in builds.items()}, launch_order_seed=20261029))
    bundles = []
    with (part/'cases.jsonl').open('x') as stream:
        for case in cases:
            stream.write(json.dumps(case, sort_keys=True)+'\n')
            inputs = part/'inputs'/case['case_id']; materialize(case, study, inputs, case['duration_minutes'])
            record = part/(case['case_id']+'.json'); write_json(record, case)
            binary, build = builds[case['model']]; bundle = part/'bundles'/case['case_id']
            stage(argparse.Namespace(case=record, inputs=inputs, binary=binary, build=build, output=bundle))
            record.unlink(); bundles.append(bundle)
    random.Random(20261029).shuffle(bundles)
    (part/'launch-order.txt').write_text(''.join(str(b)+'\n' for b in bundles))
    pinned = [out/'campaign.json', out/'study.json', out/'tools/run_mn5.sbatch', part/'cases.jsonl', part/'launch-order.txt']+[b/'manifest.json' for b in bundles]
    (out/'campaign.sha256').write_text(''.join(f'{digest(q)}  {q}\n' for q in pinned))
    print(f'Prepared {len(cases)} {a.stage} cases ({a.label}) at {out}; no jobs submitted.')


if __name__ == '__main__': main()
