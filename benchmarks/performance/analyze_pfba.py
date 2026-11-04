#!/usr/bin/env python3
"""Analyze the cancer FBA/pFBA campaign (prepare_final_studies.py --stage pfba); no simulations or submissions.

Single cell (per-step telemetry): biomass trajectory, exchange fluxes, total internal absolute flux (what pFBA
minimizes), second-stage status, exchange-ledger check and solver time.
Application (hourly snapshots): live/dead cells, live biomass, mean growth rate, share of live cells with zero growth,
mean glucose/oxygen/lactate exchange of live cells and mean field concentrations; plus infeasible primary solves,
second-stage calls/failures and wall time from the run telemetry.
pFBA is compared with FBA at the same intracellular dt; dt 0.1 with dt 0.01 for the same objective.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
from common import digest, read_json, write_json
from analyze_growth import exchange_ledger_pass

FIELDS = ('D-Glucose', 'O2', 'L-Lactate')
FLUXES = ('R_EX_glc_e', 'R_EX_o2_e', 'R_EX_lac_L_e')


def rows(path):
    if not path.is_file(): return
    with path.open() as stream: yield from csv.DictReader(stream)


def write_table(path, records):
    keys = list(dict.fromkeys(k for r in records for k in r))
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator='\n'); writer.writeheader(); writer.writerows(records)


def base(run):
    case = read_json(run/'manifest.json')['case']; metrics = read_json(run/'metrics.json')
    t = read_json(run/'inputs/benchmark_metrics.json') if (run/'inputs/benchmark_metrics.json').exists() else {}
    calls = t.get('model_optimization_calls') or 0
    return case, dict(variant=case['variant'], intracellular_dt=case['intracellular_dt_minutes'], layout=case['layout'],
        status=metrics['status'], flags=';'.join(t.get('diagnostic_flags', [])), threads=t.get('actual_threads'),
        initial_cells=t.get('initial_cells'), final_cells=t.get('final_cells'), primary_solves=calls,
        infeasible_primary_solves=t.get('solver_failures'), infeasible_share=(t.get('solver_failures') or 0)/calls if calls else None,
        stage_two_solves=t.get('stage_two_solve_calls'), stage_two_failures=t.get('stage_two_failures'), stage_two_retries=t.get('stage_two_retries'),
        stage_one_seconds=t.get('stage_one_thread_seconds'), stage_two_seconds=t.get('stage_two_thread_seconds'),
        loop_seconds=t.get('simulation_loop_seconds'), wall_seconds=metrics.get('resource', {}).get('elapsed_seconds'),
        attempt=run.name, case_id=case['case_id'])


def single(run):
    case, r = base(run)
    root = ET.parse(run/'inputs/settings.xml').getroot()
    names = {int(v.get('ID')): v.get('name') for v in root.findall('microenvironment_setup/variable')}
    mass = {round(float(x['time_minutes']), 6): float(x['total_dry_mass_pg']) for x in rows(run/'inputs/benchmark_population.csv') if x['phase'] in ('initial', 'after_cell_step', 'final')}
    flux = defaultdict(list)
    for x in rows(run/'inputs/benchmark_fluxes.csv'):
        name = names.get(int(x['field_index']))
        if name in FIELDS: flux[name].append(float(x['net_export_BioFVM_per_min']))
    cells = list(rows(run/'inputs/benchmark_cells.csv'))
    r.update(initial_dry_mass_pg=mass[min(mass)], final_dry_mass_pg=mass[max(mass)], biomass_change_percent=100*(mass[max(mass)]/mass[min(mass)]-1),
             exchange_ledger_pass=exchange_ledger_pass(rows(run/'inputs/benchmark_exchange_balance.csv')),
             median_internal_abs_flux=statistics.median(float(c['total_internal_abs_flux']) for c in cells) if cells else None,
             nonoptimal_primary=sum(c['primary_status'] != 'optimal' for c in cells),
             secondary_statuses=';'.join(f'{k}:{v}' for k, v in sorted(Counter(c['secondary_status'] for c in cells).items())))
    for name in FIELDS: r[f'mean_net_export_{name}'] = statistics.fmean(flux[name]) if flux[name] else None
    return r, mass


def application(run, density):
    import scipy.io as sio
    case, r = base(run)
    traj = []
    out = run/'inputs/output'
    for xf in sorted(out.glob('output*.xml')) + [out/'final.xml']:
        if not xf.exists(): continue
        root = ET.parse(xf).getroot(); time = float(root.findtext('.//current_time'))
        labels = {l.text: (int(l.get('index')), int(l.get('size'))) for l in root.findall('.//cell_population//labels/label')}
        c = sio.loadmat(out/root.find('.//cell_population//filename').text)['cells']
        names = [v.get('name') for v in root.findall('.//microenvironment/domain/variables/variable')]
        m = sio.loadmat(out/root.find('.//microenvironment/domain/data/filename').text)['multiscale_microenvironment']
        live = c[labels['dead'][0]] == 0
        row = dict(attempt=run.name, variant=r['variant'], intracellular_dt=r['intracellular_dt'], time_minutes=time,
                   live_cells=int(live.sum()), dead_cells=int((~live).sum()),
                   live_dry_mass_pg=float((c[labels['total_volume'][0]]*(1-c[labels['fluid_fraction'][0]])*density)[live].sum()),
                   mean_growth_per_hour=float(c[labels['growth_rate'][0]][live].mean()) if live.any() else None,
                   zero_growth_share=float((c[labels['growth_rate'][0]][live] <= 0).mean()) if live.any() else None)
        for f in FLUXES:
            if f in labels: row[f'mean_{f}'] = float(c[labels[f][0]][live].mean()) if live.any() else None
        for f in FIELDS:
            if f in names: row[f'mean_{f}_mM'] = float(m[4+names.index(f)].mean())
        traj.append(row)
    traj.sort(key=lambda x: x['time_minutes'])
    if traj:
        last = traj[-1]
        r.update({k: last[k] for k in last if k not in ('attempt', 'variant', 'intracellular_dt')})
    return r, traj


def max_rel(a, b):
    common = [t for t in a if t in b and b[t]]
    return max((abs(a[t]/b[t]-1) for t in common), default=None)


def plot(out, singles, masses, traj):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    style = {('dfba', 0.01): dict(color='#2a78d6', linestyle='-'), ('dfba', 0.1): dict(color='#2a78d6', linestyle='--'),
             ('pfba', 0.01): dict(color='#eb6834', linestyle='-'), ('pfba', 0.1): dict(color='#eb6834', linestyle='--')}
    label = lambda v, dt: f"{'FBA' if v == 'dfba' else 'pFBA'}, intracellular dt {dt:g} min"
    if singles:
        fig, ax = plt.subplots(figsize=(5.5, 3.8))
        for r in singles:
            m = masses[r['attempt']]; t = sorted(m)
            ax.plot(t, [100*(m[x]/m[t[0]]-1) for x in t], linewidth=2, label=label(r['variant'], r['intracellular_dt']), **style[(r['variant'], r['intracellular_dt'])])
        ax.set(xlabel='Simulation time (min)', ylabel='Biomass change (%)', title='Single MCF7 cell'); ax.legend(frameon=False, fontsize=8)
        ax.grid(color='#e5e5e5', linewidth=.5); fig.tight_layout(); fig.savefig(out/'single_biomass.png', dpi=160); fig.savefig(out/'single_biomass.pdf'); plt.close(fig)
    if traj:
        keys = [('live_cells', 'Live cells'), ('live_dry_mass_pg', 'Live dry mass (pg)'), ('zero_growth_share', 'Live cells with zero growth'),
                ('mean_D-Glucose_mM', 'Mean glucose (mM)'), ('mean_O2_mM', 'Mean O2 (mM)'), ('mean_L-Lactate_mM', 'Mean lactate (mM)')]
        fig, axes = plt.subplots(2, 3, figsize=(13, 7))
        runs = sorted({(x['attempt'], x['variant'], x['intracellular_dt']) for x in traj}, key=lambda x: (x[1], x[2]))
        for ax, (k, name) in zip(axes.flat, keys):
            for attempt, v, dt in runs:
                d = [x for x in traj if x['attempt'] == attempt and x.get(k) is not None]
                ax.plot([x['time_minutes']/60 for x in d], [x[k] for x in d], linewidth=2, label=label(v, dt), **style[(v, dt)])
            ax.set(xlabel='Simulation time (h)', ylabel=name); ax.grid(color='#e5e5e5', linewidth=.5)
            for side in ('top', 'right'): ax.spines[side].set_visible(False)
        axes[0, 0].legend(frameon=False, fontsize=8)
        fig.suptitle('cancer_core_metabolism application (240 cells at start), hourly snapshots', fontsize=10)
        fig.tight_layout(); fig.savefig(out/'application.png', dpi=160); fig.savefig(out/'application.pdf'); plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--plots', action='store_true'); p.add_argument('--partial', action='store_true', help='Allow missing cases (testing only)')
    a = p.parse_args()
    expected = {json.loads(l)['case_id'] for l in (a.campaign/'timestep/cases.jsonl').read_text().splitlines()}
    runs = sorted(q.parent for q in (a.campaign/'timestep/runs').glob('*/manifest.json'))
    seen = [read_json(r/'manifest.json')['case']['case_id'] for r in runs]
    if not a.partial and sorted(seen) != sorted(expected): raise ValueError('Missing, duplicated or unexpected attempts')
    singles, apps, masses, traj = [], [], {}, []
    for run in runs:
        layout = read_json(run/'manifest.json')['case']['layout']
        if layout == 'single':
            r, m = single(run); singles.append(r); masses[r['attempt']] = m
        else:
            density = float(ET.parse(run/'inputs/settings.xml').getroot().findtext('.//intracellular/growth_model/cell_density'))
            r, t = application(run, density); apps.append(r); traj.extend(t)
    pairs = []
    for group, kind in ((singles, 'single'), (apps, 'application')):
        by = {(r['variant'], r['intracellular_dt']): r for r in group}
        for (v, dt), r in sorted(by.items()):
            references = []
            if v == 'pfba': references.append((('dfba', dt), 'pfba_vs_fba'))        # same timestep, other objective
            if dt == 0.1: references.append(((v, 0.01), 'dt0.1_vs_dt0.01'))         # same objective, other timestep
            for ref_key, label in references:
                if ref_key not in by: continue
                ref = by[ref_key]; pr = dict(kind=kind, comparison=label, variant=v, intracellular_dt=dt, attempt=r['attempt'], reference=ref['attempt'])
                for k in ('final_dry_mass_pg', 'live_cells', 'live_dry_mass_pg', 'median_internal_abs_flux', 'loop_seconds', 'wall_seconds',
                          'infeasible_share', 'mean_net_export_D-Glucose', 'mean_net_export_O2', 'mean_net_export_L-Lactate',
                          'mean_R_EX_glc_e', 'mean_R_EX_o2_e', 'mean_R_EX_lac_L_e'):
                    x, y = r.get(k), ref.get(k)
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)) and y: pr[f'{k}_ratio'] = x/y
                if kind == 'single': pr['max_biomass_rel_diff'] = max_rel(masses[r['attempt']], masses[ref['attempt']])
                else:
                    for k in ('live_dry_mass_pg', 'live_cells'):
                        A = {x['time_minutes']: x[k] for x in traj if x['attempt'] == r['attempt']}; B = {x['time_minutes']: x[k] for x in traj if x['attempt'] == ref['attempt']}
                        pr[f'max_{k}_rel_diff'] = max_rel(A, B)
                pairs.append(pr)
    a.output.mkdir(parents=True, exist_ok=False); (a.output/'tables').mkdir(); (a.output/'data').mkdir()
    copied = {}
    for run in runs:
        dest = a.output/'data'/run.name; dest.mkdir()
        for f in [run/n for n in ('manifest.json', 'metrics.json', 'hardware.json', 'stdout.log', 'stderr.log', 'resource.tsv')] + \
                 [run/'inputs'/n for n in ('benchmark_metrics.json', 'settings.xml', 'benchmark_update_counts.csv')]:
            if f.exists(): (dest/f.name).write_bytes(f.read_bytes()); copied[str((dest/f.name).relative_to(a.output))] = digest(f)
    if singles: write_table(a.output/'tables/single_runs.csv', singles)
    if apps: write_table(a.output/'tables/application_runs.csv', apps); write_table(a.output/'tables/application_trajectories.csv', traj)
    if pairs: write_table(a.output/'tables/comparisons.csv', pairs)
    write_json(a.output/'analysis.json', dict(script_sha256=digest(__file__), campaign=str(a.campaign.resolve()), attempts=len(runs),
        expected_cases=len(expected), missing=sorted(expected-set(seen)), evidence_sha256=copied))
    if a.plots: (a.output/'plots').mkdir(); plot(a.output/'plots', singles, masses, traj)
    for r in singles + apps: print({k: r.get(k) for k in ('layout', 'variant', 'intracellular_dt', 'status', 'flags', 'final_cells', 'infeasible_share', 'stage_two_failures', 'biomass_change_percent', 'live_cells', 'live_dry_mass_pg', 'wall_seconds')})
    for pr in pairs: print(pr)


if __name__ == '__main__': main()
