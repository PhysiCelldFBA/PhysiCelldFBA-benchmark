#!/usr/bin/env python3
"""Prepare the cancer FBA/pFBA comparison or the performance/scaling study; never submits or runs simulations.

Stages:
  pfba     MCF7 core, FBA and pFBA (fraction of optimum 1) at intracellular dt 0.01 and 0.1 min, diffusion dt 0.01:
           - one fixed cell for 240 min with per-step telemetry (diagnostic_endpoints, 1 thread);
           - the cancer_core_metabolism application (its 240-cell CSV, normal multicellular behaviour) for its
             4320 min, with hourly snapshots and no per-step telemetry (snapshots_hourly), 56 threads.
  scaling  the agreed 'main' performance design: 100/1000/10000 cells at 1 and 56 threads, 1-112 threads at 1000
           cells, field counts at 1000 cells and 56 threads; E. coli core, MCF7 core, iML1515; PhysiCelldFBA with and
           without metabolism and upstream PhysiCell; 3 repeats; k = 1 at diffusion dt 0.01; minimal output.
Each stage writes one case list per Slurm job (launch-<group>.txt), pinned in campaign.sha256.
"""
import argparse
import copy
import csv
import json
from pathlib import Path
import random
import shutil
import subprocess
import xml.etree.ElementTree as ET
from common import REPO, digest, read_json, source_path, write_json
from design import plan_cases
from inputs import materialize
from prepare import stage

HERE = Path(__file__).resolve().parent
PFBA_DTS = (0.01, 0.1)
SEED = 20261104


def pfba_cases(study, single_minutes, application_minutes, application_threads):
    cases = []
    for dt in PFBA_DTS:
        s = copy.deepcopy(study); s['pfba']['selected_dt_minutes'] = dt
        for phase in ('pfba', 'pfba_application'):
            for case in plan_cases(s, phase):
                application = case['layout'] == 'application'
                if application:
                    template = source_path(case['template'])
                    name = ET.parse(template).getroot().findtext('initial_conditions/cell_positions/filename')
                    with (template.parent/name).open(newline='') as stream: cells = sum(1 for _ in csv.DictReader(stream))
                    case.update(cells_requested=cells, threads=application_threads, output_policy='snapshots_hourly',
                                duration_minutes=application_minutes, group=f"application-{case['variant']}-dt{dt}")
                else:
                    case.update(output_policy='diagnostic_endpoints', duration_minutes=single_minutes, group='single')
                case.update(status='ready', open_decisions=[], interpretation='cancer_fba_pfba_comparison',
                            validation_record='FBA and pFBA differ only in the secondary objective; retain every flag and second-stage failure.')
                case['case_id'] += f'-dt{dt}'.replace('.', '_')
                cases.append(case)
    return cases


def scaling_cases(study, minutes):
    cases = []
    for case in plan_cases(study, 'main'):
        case.update(status='ready', open_decisions=[], duration_minutes=minutes, interpretation='performance_scaling',
                    validation_record='Performance workload from the validated medium profile; minimal output; identical workload across variants.',
                    group=f"{case['model']}-{case['variant']}-n{case['cells_requested']}-p{case['threads']}-f{case['fields']}")
        cases.append(case)
    return cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=('pfba', 'scaling'), required=True)
    for name in ('unit-binary', 'unit-build', 'cancer-binary', 'cancer-build', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--upstream-binary', type=Path); p.add_argument('--upstream-build', type=Path)
    p.add_argument('--single-minutes', type=float, default=240); p.add_argument('--application-minutes', type=float, default=4320)
    p.add_argument('--application-threads', type=int, default=56); p.add_argument('--scaling-minutes', type=float, default=10)
    p.add_argument('--label', required=True)
    a = p.parse_args()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).strip():
        raise ValueError('Commit preparation sources before staging')
    study = read_json(HERE/'study.json')
    cases = pfba_cases(study, a.single_minutes, a.application_minutes, a.application_threads) if a.stage == 'pfba' else scaling_cases(study, a.scaling_minutes)
    builds = {'ecoli_core': (a.unit_binary, a.unit_build), 'iml1515': (a.unit_binary, a.unit_build), 'mcf7_core': (a.cancer_binary, a.cancer_build)}
    if any(c['variant'] == 'upstream_physicell' for c in cases):
        if not a.upstream_binary or not a.upstream_build: raise ValueError('The scaling stage needs --upstream-binary and --upstream-build')
        builds['upstream'] = (a.upstream_binary, a.upstream_build)
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
        purpose=a.stage, label=a.label, cases=len(cases), launch_order_seed=SEED,
        builds={k: read_json(r)['binary_sha256'] for k, (_, r) in builds.items()},
        settings=dict(single_minutes=a.single_minutes, application_minutes=a.application_minutes, application_threads=a.application_threads,
                      scaling_minutes=a.scaling_minutes, pfba_intracellular_dt_minutes=list(PFBA_DTS))))
    bundles, groups = [], {}
    with (part/'cases.jsonl').open('x') as stream:
        for case in cases:
            stream.write(json.dumps(case, sort_keys=True)+'\n')
            inputs = part/'inputs'/case['case_id']; materialize(case, study, inputs, case['duration_minutes'])
            record = part/(case['case_id']+'.json'); write_json(record, case)
            binary, build = builds['upstream' if case['variant'] == 'upstream_physicell' else case['model']]
            bundle = part/'bundles'/case['case_id']
            stage(argparse.Namespace(case=record, inputs=inputs, binary=binary, build=build, output=bundle))
            record.unlink(); bundles.append(bundle); groups.setdefault(case['group'], []).append(bundle)
    random.Random(SEED).shuffle(bundles)
    (part/'launch-order.txt').write_text(''.join(str(b)+'\n' for b in bundles))
    lists = [part/'launch-order.txt']
    for name, members in sorted(groups.items()):
        path = part/f'launch-{name}.txt'.replace('.', '_').replace('_txt', '.txt')
        path.write_text(''.join(str(b)+'\n' for b in members)); lists.append(path)
    pinned = [out/'campaign.json', out/'study.json', out/'tools/run_mn5.sbatch', part/'cases.jsonl']+lists+[b/'manifest.json' for b in bundles]
    (out/'campaign.sha256').write_text(''.join(f'{digest(q)}  {q}\n' for q in pinned))
    print(f'Prepared {len(cases)} {a.stage} cases in {len(groups)} groups ({a.label}) at {out}; no jobs submitted.')


if __name__ == '__main__': main()
