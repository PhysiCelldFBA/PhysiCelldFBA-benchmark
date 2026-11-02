#!/usr/bin/env python3
"""Prepare a timestep trade-off campaign (TIMESTEP_TRADEOFF.md); never submits or runs simulations.

Stages:
  checks    ratio-1 depletion runs of scenarios A1-A4 and iML1515 single-cell runs at k = 1, 10, 100
  accuracy  scenarios A1-A4 at every ratio, plus a diffusion-dt 0.005 reference of A3
  cost-pilot / cost
            Part B: the 1000-cell performance workloads (lattice, fed medium, fixed volume,
            minimal output) of E. coli core, MCF7 core and iML1515 at 1 and 56 threads;
            the pilot uses k = 1, 10, 100 and one repeat, the full stage every ratio and 3 repeats
Accuracy cases are serial with fixed positions and population; metabolic biomass growth is on.
"""
import argparse
import copy
import json
from pathlib import Path
import random
import shutil
import subprocess
from common import REPO, SOURCE as ROOT, config_metadata, digest, read_json, source_path, write_json
from design import plan_cases
from inputs import materialize
from prepare import stage

HERE = Path(__file__).resolve().parent
RATIOS = (1, 2, 5, 10, 20, 50, 100)
DIFFUSION_DT = 0.01
# id: (model, template or medium profile, cells)
SCENARIOS = {
    'A1': ('ecoli_core', None, 1),               # unit-test mass conversion, 10 mM glucose; voxel size from the template
    'A2': ('ecoli_core', 'ecoli_colony_fed', 16),  # bacterial-colony medium and voxels
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
                fixed_population=True, fixed_volume=False, fields=config_metadata(source_path(template))['fields'],
                diffusion_dt_minutes=diffusion_dt, intracellular_dt_minutes=round(diffusion_dt*ratio, 12), ratio=ratio,
                duration_minutes=duration, output_policy='diagnostic_endpoints', status='ready', open_decisions=[],
                interpretation='timestep_tradeoff_accuracy', order_seed=None,
                validation_record='Serial trade-off case: fixed positions/population, biomass growth on; retain every flag.')
    case.pop('medium_profile', None)
    if profile_id: case['medium_profile'] = profile_id
    case['case_id'] = f'{phase}-{scenario}-{model}-n{cells}-q{ratio}-d{diffusion_dt}'.replace('.', '_')
    return case


def cost_cases(study, ratios, repeats, duration, diffusion_dt):
    """Copy the validated 1000-cell performance workloads and vary only k and the repeat."""
    cases = []
    for base in plan_cases(study, 'pilot'):
        if base['variant'] != 'dfba' or base['cells_requested'] != 1000 or base['repeat'] != 1: continue
        for k in ratios:
            for r in range(1, repeats+1):
                case = copy.deepcopy(base)
                case.update(phase='tradeoff_cost', scenario='B-'+base['model'], ratio=k, repeat=r,
                            diffusion_dt_minutes=diffusion_dt, intracellular_dt_minutes=round(diffusion_dt*k, 12), duration_minutes=duration,
                            status='ready', open_decisions=[], interpretation='timestep_tradeoff_cost',
                            validation_record='Performance workload from the validated medium profile; only k and repeat vary. Timing run with minimal output.')
                case['case_id'] = f"tradeoff_cost-{base['model']}-n1000-p{base['threads']}-f{base['fields']}-q{k}-d{diffusion_dt}-r{r}".replace('.', '_')
                cases.append(case)
    if {c['threads'] for c in cases} != {1, 56} or len({c['model'] for c in cases}) != 3:
        raise ValueError('Expected the 1000-cell workloads of three models at 1 and 56 threads')
    return cases


def cases_for_stage(study, name, duration, diffusion_dt=DIFFUSION_DT):
    if name == 'cost-pilot': return cost_cases(study, (1, 10, 100), 1, duration, diffusion_dt)
    if name == 'cost': return cost_cases(study, RATIOS, 3, duration, diffusion_dt)
    base = plan_cases(study, 'timestep')[0]
    if name == 'checks':
        cases = [case_for(study, base, 'tradeoff_check', s, 1, duration, diffusion_dt) for s in ('A1', 'A2', 'A3', 'A4')]
        cases += [case_for(study, base, 'tradeoff_check', 'I1', k, min(duration, 60), diffusion_dt) for k in (1, 10, 100)]
    else:
        cases = [case_for(study, base, 'tradeoff_accuracy', s, k, duration, diffusion_dt) for s in ('A1', 'A2', 'A3', 'A4') for k in RATIOS]
        cases.append(case_for(study, base, 'tradeoff_accuracy', 'A3', 1, duration, diffusion_dt=diffusion_dt/2))
    return cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=('checks', 'accuracy', 'cost-pilot', 'cost'), required=True)
    for name in ('unit-binary', 'unit-build', 'cancer-binary', 'cancer-build', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--duration', type=float, required=True, help='Simulated minutes (iML1515 checks use at most 60)')
    p.add_argument('--label', required=True, help='Build label recorded in campaign.json, e.g. proposed-fix or development')
    p.add_argument('--diffusion-dt', type=float, default=DIFFUSION_DT, help='Diffusion time step in minutes (default 0.01); intracellular dt = k times this')
    a = p.parse_args()
    if a.duration < 10: raise ValueError('Use at least 10 simulated minutes')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).strip():
        raise ValueError('Commit preparation sources before staging')
    study = read_json(HERE/'study.json'); cases = cases_for_stage(study, a.stage, a.duration, a.diffusion_dt)
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
        duration_minutes=a.duration, diffusion_dt_minutes=a.diffusion_dt, cases=len(cases), scenarios={k: list(v) for k, v in SCENARIOS.items()},
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
    lists = [part/'launch-order.txt']
    if a.stage.startswith('cost'):
        # One list per model, thread count and k, each submitted as its own job; repeats share one node.
        groups = {}
        for b, case in zip(bundles, (read_json(b/'manifest.json')['case'] for b in bundles)):
            groups.setdefault(f"launch-{case['model']}-p{case['threads']}-q{case['ratio']}.txt", []).append(b)
        for name, members in sorted(groups.items()):
            (part/name).write_text(''.join(str(b)+'\n' for b in members)); lists.append(part/name)
    pinned = [out/'campaign.json', out/'study.json', out/'tools/run_mn5.sbatch', part/'cases.jsonl']+lists+[b/'manifest.json' for b in bundles]
    (out/'campaign.sha256').write_text(''.join(f'{digest(q)}  {q}\n' for q in pinned))
    print(f'Prepared {len(cases)} {a.stage} cases ({a.label}) at {out}; no jobs submitted.')


if __name__ == '__main__': main()
