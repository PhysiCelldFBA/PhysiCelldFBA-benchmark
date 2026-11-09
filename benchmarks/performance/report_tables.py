#!/usr/bin/env python3
"""Summary tables for the final report from existing results; no simulations or submissions.

  models.csv          SBML size and the LP size the solver sees, per model
  solver.csv          primary solves, time per solve and simplex iterations per solve (1000 cells, 1 thread, k = 1)
  feasible_sizes.csv  measured loop cost per cell and simulated hour, and wall time extrapolated linearly to
                      larger problems (k = 1, diffusion dt 0.01 min)
  environment.json    hardware, compiler, libraries and solver settings of the final runs
"""
import argparse
import csv
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
from common import read_json, source_path, write_json

HERE = Path(__file__).resolve().parent
CELLS = (1000, 10000, 100000)
HOURS = 24


def write_table(path, records):
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator='\n'); writer.writeheader(); writer.writerows(records)


def sbml_size(path):
    root = ET.parse(path).getroot(); ns = root.tag.split('}')[0] + '}' if root.tag.startswith('{') else ''
    model = root.find(f'{ns}model')
    def count(tag):
        node = model.find(f'{ns}{tag}')
        return len(node) if node is not None else 0
    return dict(reactions=count('listOfReactions'), species=count('listOfSpecies'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scaling', type=Path, required=True, help='scaling report folder (analyze_scaling.py output)')
    p.add_argument('--builds', type=Path, required=True, help='folder with the final build records')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    study = read_json(HERE/'study.json'); profiles = read_json(HERE/'growth_profiles.json')
    data = a.scaling/'data'
    runs = []
    for d in sorted(data.iterdir()):
        case = read_json(d/'manifest.json')['case']
        if case['variant'] != 'dfba': continue
        runs.append((case, read_json(d/'benchmark_metrics.json'), d))
    models, solver = [], []
    for model in ('ecoli_core', 'mcf7_core', 'iml1515'):
        profile = profiles[study['performance_medium_profiles'][model]]
        size = sbml_size(source_path(profile['sbml']))
        ref = [(c, t) for c, t, _ in runs if c['model'] == model and c['cells_requested'] == 1000 and c['threads'] == 1]
        t = ref[0][1]
        models.append(dict(model=model, sbml=profile['sbml'], sbml_reactions=size['reactions'], sbml_species=size['species'],
                           lp_rows=t['stage_one_rows_max'], lp_columns=t['stage_one_columns_max'], lp_nonzeros=t['stage_one_nonzeros_max']))
        per = [(x['solver_thread_seconds']/x['stage_one_solve_calls'], x['stage_one_iterations']/x['stage_one_solve_calls'],
                x['initial_primary_thread_seconds']/x['initial_primary_solve_calls']) for _, x in ref]
        solver.append(dict(model=model, repeats=len(ref), solves_per_run=t['stage_one_solve_calls'],
                           microseconds_per_warm_solve=round(1e6*statistics.median(v[0] for v in per), 2),
                           simplex_iterations_per_warm_solve=round(statistics.median(v[1] for v in per), 4),
                           milliseconds_per_initial_solve=round(1e3*statistics.median(v[2] for v in per), 3),
                           warm_solves_per_second_one_thread=round(1/statistics.median(v[0] for v in per))))
    summary = list(csv.DictReader((a.scaling/'tables/summary.csv').open()))
    feasible = []
    for model in ('ecoli_core', 'mcf7_core', 'iml1515'):
        for threads in (1, 56):
            rows = [s for s in summary if s['model'] == model and s['variant'] == 'dfba' and int(s['threads']) == threads and s['reference_fields'] == 'True']
            biggest = max(rows, key=lambda s: int(s['cells']))
            per_cell_hour = float(biggest['loop_seconds'])/int(biggest['cells'])*6   # measured over 10 min -> per simulated hour
            r = dict(model=model, threads=threads, measured_at_cells=int(biggest['cells']), loop_seconds_per_cell_per_simulated_hour=round(per_cell_hour, 4))
            for n in CELLS: r[f'wall_hours_{n}_cells_{HOURS}h'] = round(per_cell_hour*n*HOURS/3600, 2)
            feasible.append(r)
    a.output.mkdir(parents=True, exist_ok=True)
    write_table(a.output/'models.csv', models); write_table(a.output/'solver.csv', solver); write_table(a.output/'feasible_sizes.csv', feasible)
    # hardware, compiler, libraries and solver settings of the final runs
    _, _, d = next(r for r in runs if r[0]['model'] == 'iml1515' and r[0]['threads'] == 56)
    hw = read_json(d/'hardware.json'); build = read_json(a.builds/'fix-unit.json')
    lscpu = hw['lscpu'] if isinstance(hw['lscpu'], dict) else {}
    write_json(a.output/'environment.json', dict(
        node=hw.get('node') or hw.get('hostname'), lscpu=lscpu, memory=hw.get('memory'), uname=hw.get('uname'),
        modules=hw.get('modules'), thread_environment=hw.get('thread_environment'), solver_environment=hw.get('solver_environment'),
        compiler=build['compiler'].splitlines()[0], compiler_flags=build['compiler_flags'],
        libraries=build['libraries'].get('versions'), solver_settings=build['solver_settings'],
        physicelldfba_commit=build['source_commit'], upstream_physicell_commit=read_json(a.builds/'upstream-template.json')['source_commit']))
    for name in ('models', 'solver', 'feasible_sizes'):
        print(f'== {name}'); print((a.output/f'{name}.csv').read_text())


if __name__ == '__main__': main()
