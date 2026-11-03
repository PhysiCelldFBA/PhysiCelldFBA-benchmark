#!/usr/bin/env python3
"""Analyze timestep trade-off campaigns (prepare_tradeoff.py); no simulations or submissions.

Uptake is the substrate the cells actually removed: the sum of the exchange ledger's
observed changes during the cell-exchange step, so boundary supply does not hide it.
Errors are relative to k = 1 of the same build and scenario at the campaign's diffusion dt.
Every attempt is retained; nothing is clipped or dropped.
"""
import argparse
from collections import defaultdict
import csv
import math
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from common import digest, read_json, write_json
from analyze_growth import exchange_ledger_pass

NUTRIENTS = ('glucose', 'd-glucose', 'oxygen', 'o2')
SAMPLE_EVERY_MINUTES = 1.0
GRID_MINUTES = 0.01      # biomass grid for errors: a multiple of every diffusion dt used (0.01, 0.005, 0.001, 0.0005)


def rows(path):
    """Rows one at a time: per-step tables reach millions of rows at diffusion dt 0.001."""
    if not path.is_file(): return
    with path.open() as stream: yield from csv.DictReader(stream)


def on_grid(time, step):
    """Time rounded to the nearest multiple of step (minutes), or None if it is not one."""
    n = round(time/step)
    return round(n*step, 6) if abs(time/step - n) < 1e-6 else None


def write_table(path, records):
    keys = list(dict.fromkeys(k for r in records for k in r))
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator='\n'); writer.writeheader(); writer.writerows(records)


def nutrient(name):
    n = name.lower()
    return 'glucose' if n in ('glucose', 'd-glucose') else 'oxygen' if n in ('oxygen', 'o2') else None


def inspect(run, label):
    manifest = read_json(run/'manifest.json'); case = manifest['case']
    metrics = read_json(run/'metrics.json'); t = metrics.get('telemetry') or {}
    root = ET.parse(run/'inputs/settings.xml').getroot()
    names = {int(v.get('ID')): v.get('name') for v in root.findall('microenvironment_setup/variable')}
    # Biomass on a 0.01-min grid (shared by every diffusion dt used) for the error comparison; first and last values kept.
    mass = {}; m0 = mf = None
    for r in rows(run/'inputs/benchmark_population.csv'):
        if r['phase'] not in ('initial', 'after_cell_step', 'final'): continue
        value = float(r['total_dry_mass_pg']); m0 = value if m0 is None else m0; mf = value
        key = on_grid(float(r['time_minutes']), GRID_MINUTES)
        if key is not None: mass[key] = value
    uptake = defaultdict(float); cumulative = defaultdict(dict)
    for r in rows(run/'inputs/benchmark_exchange_balance.csv'):
        n = nutrient(names[int(r['field_index'])])
        if not n: continue
        uptake[n] -= float(r['observed_delta'])
        key = on_grid(float(r['time_minutes']), SAMPLE_EVERY_MINUTES)
        if key is not None: cumulative[n][key] = uptake[n]
    ledger_pass = exchange_ledger_pass(rows(run/'inputs/benchmark_exchange_balance.csv'))
    minimum = defaultdict(lambda: math.inf); amount = defaultdict(dict); initial = {}; depleted = defaultdict(dict)
    for r in rows(run/'inputs/benchmark_substrates.csv'):
        n = nutrient(r['field_name'])
        if not n: continue
        minimum[n] = min(minimum[n], float(r['min_concentration']))
        if r['phase'] not in ('initial', 'after_cell_step'): continue
        time, value = float(r['time_minutes']), float(r['amount_concentration_um3'])
        initial.setdefault(n, value)
        for level in (50, 10):
            if level not in depleted[n] and initial[n] > 0 and value <= initial[n]*level/100: depleted[n][level] = time
        key = on_grid(time, SAMPLE_EVERY_MINUTES)
        if key is not None: amount[n][key] = value
    nonoptimal = sum(c['primary_status'] != 'optimal' for c in rows(run/'inputs/benchmark_cells.csv'))
    record = dict(build=label, scenario=case['scenario'], model=case['model'], cells=case['cells_requested'], ratio=case['ratio'],
        diffusion_dt_minutes=case['diffusion_dt_minutes'], intracellular_dt_minutes=case['intracellular_dt_minutes'],
        duration_minutes=case['duration_minutes'], status=metrics['status'], flags=';'.join(t.get('diagnostic_flags', [])),
        updates=t.get('intracellular_updates'), nonoptimal_updates=nonoptimal,
        solver_failures=t.get('solver_failures', 0), exchange_ledger_pass=ledger_pass,
        initial_dry_mass_pg=m0, final_dry_mass_pg=mf, biomass_change_percent=100*(mf/m0-1),
        wall_seconds=metrics.get('resource', {}).get('elapsed_seconds'), attempt=run.name, case_id=case['case_id'])
    for n in ('glucose', 'oxygen'):
        record[f'{n}_uptake_mM_um3'] = uptake[n] if n in uptake else None
        record[f'{n}_min_mM'] = minimum[n] if n in minimum else None
        if n in initial:
            for level in (50, 10): record[f'{n}_domain_{level}pct_minute'] = depleted[n].get(level)
    record['yield_pg_per_mM_um3_glucose'] = (mf-m0)/uptake['glucose'] if uptake.get('glucose') else None
    samples = []
    for time in sorted(mass):
        if on_grid(time, SAMPLE_EVERY_MINUTES) is None: continue
        s = dict(build=label, scenario=case['scenario'], ratio=case['ratio'], diffusion_dt_minutes=case['diffusion_dt_minutes'],
                 time_minutes=time, dry_mass_pg=mass[time])
        for n in ('glucose', 'oxygen'):
            s[f'{n}_domain_mM_um3'] = amount.get(n, {}).get(time)
            s[f'{n}_uptake_mM_um3'] = cumulative.get(n, {}).get(time)
        samples.append(s)
    return record, samples, mass


def relative(a, b):
    return None if a is None or b in (None, 0) else (a-b)/abs(b)


def errors(records, masses):
    # Reference: k = 1 at the campaign's diffusion dt (the largest among a scenario's k = 1 runs; the other is the dt/2 check).
    reference = {}
    for r in records:
        key = (r['build'], r['scenario'])
        if r['ratio'] == 1 and (key not in reference or r['diffusion_dt_minutes'] > reference[key]['diffusion_dt_minutes']): reference[key] = r
    for r in records:
        ref = reference.get((r['build'], r['scenario']))
        if ref is None: continue
        r['final_biomass_rel_error'] = relative(r['final_dry_mass_pg'], ref['final_dry_mass_pg'])
        a, b = masses[r['attempt']], masses[ref['attempt']]
        common = [time for time in a if time in b]
        r['max_biomass_rel_error'] = max((abs(relative(a[time], b[time])) for time in common), default=None)
        r['trajectory_samples_compared'] = len(common)
        for key in ('glucose_uptake_mM_um3', 'oxygen_uptake_mM_um3', 'yield_pg_per_mM_um3_glucose'):
            r[key.replace('_mM_um3', '').replace('_pg_per', '_per')+'_rel_error'] = relative(r[key], ref[key])


def plot_checks(out, records, samples):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    scenarios = sorted({r['scenario'] for r in records if r['scenario'].startswith('A')})
    fig, axes = plt.subplots(3, len(scenarios), figsize=(4.2*len(scenarios), 8.5), squeeze=False)
    for col, s in enumerate(scenarios):
        data = [x for x in samples if x['scenario'] == s and x['ratio'] == 1]
        t = [x['time_minutes'] for x in data]
        axes[0, col].plot(t, [x['dry_mass_pg'] for x in data], color='#2a78d6', linewidth=2)
        for n, color in (('glucose', '#2a78d6'), ('oxygen', '#eb6834')):
            v = [x[f'{n}_domain_mM_um3'] for x in data]
            if any(y is not None for y in v) and v[0]:
                axes[1, col].plot(t, [y/v[0] if y is not None else None for y in v], color=color, linewidth=2, label=n)
            u = [x[f'{n}_uptake_mM_um3'] for x in data]
            if any(y is not None for y in u): axes[2, col].plot(t, u, color=color, linewidth=2, label=n)
        r = next(x for x in records if x['scenario'] == s)
        axes[0, col].set_title(f"{s}: {r['model']}, {r['cells']} cell{'s' if r['cells'] > 1 else ''}")
        axes[1, col].legend(frameon=False); axes[2, col].set_xlabel('Simulation time (min)')
        for row in range(3):
            axes[row, col].grid(color='#e5e5e5', linewidth=.5)
            for side in ('top', 'right'): axes[row, col].spines[side].set_visible(False)
    axes[0, 0].set_ylabel('Total dry mass (pg)'); axes[1, 0].set_ylabel('Domain amount / initial')
    axes[2, 0].set_ylabel('Cumulative cell uptake (mM·µm³)')
    fig.suptitle(f"Trade-off runs at k = 1 (diffusion dt {max(r['diffusion_dt_minutes'] for r in records):g} min)", fontsize=10)
    fig.tight_layout(); fig.savefig(out/'checks.png', dpi=160); fig.savefig(out/'checks.pdf'); plt.close(fig)


def plot_accuracy(out, records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    builds = sorted({r['build'] for r in records})
    style = dict(zip(builds, (dict(color='#eb6834', marker='s'), dict(color='#2a78d6', marker='o'))))
    scenarios = sorted({r['scenario'] for r in records})
    metrics = (('max_biomass_rel_error', 'Max |biomass error| vs k = 1'), ('glucose_uptake_rel_error', '|Glucose uptake error| vs k = 1'))
    fig, axes = plt.subplots(len(metrics), len(scenarios), figsize=(4.2*len(scenarios), 7), squeeze=False)
    for col, s in enumerate(scenarios):
        for b in builds:
            data = sorted((r for r in records if r['scenario'] == s and r['build'] == b and r['diffusion_dt_minutes'] == max(x['diffusion_dt_minutes'] for x in records) and r['ratio'] > 1), key=lambda r: r['ratio'])
            for row, (key, _) in enumerate(metrics):
                pts = [(r['ratio'], abs(r[key])) for r in data if r.get(key) is not None]
                if pts:
                    axes[row, col].plot(*zip(*pts), linewidth=2, markersize=6, label=b, **style[b])
                    failed = [(x, y) for (x, y), r in zip(pts, [r for r in data if r.get(key) is not None]) if not r['exchange_ledger_pass'] or r['nonoptimal_updates']]
                    if failed: axes[row, col].scatter(*zip(*failed), s=120, facecolors='none', edgecolors='#333333', linewidths=1.2)
        axes[0, col].set_title(s)
        for row in range(len(metrics)):
            ax = axes[row, col]; ax.set_xscale('log'); ax.set_yscale('log')
            ax.set_xticks([2, 5, 10, 20, 50, 100]); ax.set_xticklabels(['2', '5', '10', '20', '50', '100'])
            ax.grid(color='#e5e5e5', linewidth=.5)
            for side in ('top', 'right'): ax.spines[side].set_visible(False)
        axes[-1, col].set_xlabel('k = intracellular dt / diffusion dt')
    for row, (_, label) in enumerate(metrics): axes[row, 0].set_ylabel(label)
    axes[0, 0].legend(title='Build (ring: ledger or LP failure)', frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(out/'accuracy.png', dpi=160); fig.savefig(out/'accuracy.pdf'); plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', nargs=2, action='append', required=True, metavar=('LABEL', 'PATH'))
    p.add_argument('--output', type=Path, required=True); p.add_argument('--plots', action='store_true')
    a = p.parse_args()
    records, samples, masses, copied = [], [], {}, {}
    for label, path in a.campaign:
        campaign = Path(path)
        expected = {r['case_id'] for r in map(__import__('json').loads, (campaign/'timestep/cases.jsonl').read_text().splitlines())}
        runs = sorted(q.parent for q in (campaign/'timestep/runs').glob('*/manifest.json'))
        seen = [read_json(r/'manifest.json')['case']['case_id'] for r in runs]
        if sorted(seen) != sorted(expected): raise ValueError(f'{label}: missing, duplicated or unexpected attempts')
        for run in runs:
            record, s, mass = inspect(run, label)
            records.append(record); samples.extend(s); masses[run.name] = mass
    errors(records, masses)
    a.output.mkdir(parents=True, exist_ok=False)
    for folder in ('tables', 'data'): (a.output/folder).mkdir()
    for (label, path), run in ((lp, r) for lp in a.campaign for r in sorted(q.parent for q in (Path(lp[1])/'timestep/runs').glob('*/manifest.json'))):
        dest = a.output/'data'/label/run.name; dest.mkdir(parents=True)
        for f in [run/n for n in ('manifest.json', 'metrics.json', 'hardware.json', 'stdout.log', 'stderr.log', 'resource.tsv')] + \
                 [run/'inputs'/n for n in ('settings.xml', 'benchmark_metrics.json', 'benchmark_update_counts.csv')]:
            if f.exists(): shutil.copy2(f, dest/f.name); copied[str((dest/f.name).relative_to(a.output))] = digest(f)
    order = lambda r: (r['scenario'], r['build'], r['diffusion_dt_minutes'], r['ratio'])
    write_table(a.output/'tables/runs.csv', sorted(records, key=order))
    write_table(a.output/'tables/trajectories_1min.csv', samples)
    write_json(a.output/'analysis.json', dict(script_sha256=digest(__file__), campaigns={l: str(Path(p).resolve()) for l, p in a.campaign},
        attempts=len(records), evidence_sha256=copied,
        note='Uptake = -sum(observed_delta) of the exchange ledger; errors relative to k = 1 at the campaign diffusion dt, same build and scenario; biomass errors on a 0.01-min grid.'))
    if a.plots:
        (a.output/'plots').mkdir()
        if any(r['scenario'].startswith('A') and r['ratio'] == 1 for r in records): plot_checks(a.output/'plots', records, samples)
        if any(r['ratio'] > 1 and r['scenario'].startswith('A') for r in records): plot_accuracy(a.output/'plots', [r for r in records if r['scenario'].startswith('A')])
    for r in sorted(records, key=order):
        print({k: r[k] for k in ('build', 'scenario', 'ratio', 'status', 'flags', 'updates', 'nonoptimal_updates', 'exchange_ledger_pass',
                                 'biomass_change_percent', 'glucose_uptake_mM_um3', 'glucose_min_mM', 'oxygen_min_mM',
                                 'glucose_domain_50pct_minute', 'glucose_domain_10pct_minute', 'oxygen_domain_50pct_minute',
                                 'final_biomass_rel_error', 'glucose_uptake_rel_error', 'wall_seconds') if k in r})


if __name__ == '__main__': main()
