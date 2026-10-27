#!/usr/bin/env python3
"""Compare timestep-pilot reports (analyze_pilots.py) from two builds; no simulations or submissions.

For each model and ratio: biomass change, glucose consumed (absolute and relative to
ratio 1 of the same build), yield-based biomass error, minimum glucose, solver failures
and the exchange-ledger check applied to every recorded step of every run. Ratio-1
trajectories are also compared across builds.
"""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
from common import digest, read_json, write_json
from analyze_growth import exchange_ledger_pass


def rows(path):
    with Path(path).open() as stream: return list(csv.DictReader(stream))


def number(value):
    try: return float(value)
    except (TypeError, ValueError): return None


def write_table(path, records):
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(records)


def ledger_pass(campaign, case_id):
    """Exchange ledger over all fields of the run's single recorded attempt."""
    runs = [p.parent for p in (campaign/'timestep/runs').glob('*/manifest.json') if read_json(p)['case']['case_id'] == case_id]
    if len(runs) != 1: raise ValueError(f'Expected one attempt for {case_id}, found {len(runs)}')
    ledger = rows(runs[0]/'inputs/benchmark_exchange_balance.csv')
    return exchange_ledger_pass(ledger)


def load(report, campaign, label):
    out = []
    for r in rows(report/'tables/outcomes.csv'):
        out.append(dict(build=label, model=r['model'], phase=r['phase'], ratio=number(r['ratio']),
            diffusion_dt_minutes=number(r['diffusion_dt_minutes']), intracellular_dt_minutes=number(r['intracellular_dt_minutes']),
            actual_updates=int(float(r['actual_updates'])), solver_failures=int(float(r['solver_failures'] or 0)),
            biomass_change_percent=number(r['biomass_change_percent']),
            glucose_consumed_percent=None if number(r['glucose_remaining_fraction']) is None else 100*(1-number(r['glucose_remaining_fraction'])),
            biomass_error_fraction=number(r['biomass_error_fraction']), minimum_glucose_mM=number(r['minimum_glucose_mM']),
            exchange_max_abs_residual=number(r['exchange_max_abs_residual']),
            exchange_ledger_pass=ledger_pass(campaign, r['case_id']), wall_seconds=number(r['wall_seconds']),
            flags=r['flags'], case_id=r['case_id']))
    return out


def plot(out, records, labels):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    style = {labels[0]: dict(color='#2a78d6', marker='o'), labels[1]: dict(color='#eb6834', marker='s')}
    models = sorted({r['model'] for r in records})
    fig, axes = plt.subplots(2, len(models), figsize=(5.2*len(models), 7), squeeze=False)
    for col, model in enumerate(models):
        for label in labels:
            data = sorted((r for r in records if r['build'] == label and r['model'] == model and r['phase'] == 'timestep'), key=lambda r: r['ratio'])
            # A domain whose total glucose rises (boundary supply) does not measure uptake.
            supplied = any(r['glucose_consumed_percent'] is not None and r['glucose_consumed_percent'] < 0 for r in data)
            for row, key in enumerate(('glucose_consumed_percent', 'biomass_change_percent')):
                if row == 0 and supplied: continue
                xs = [r['ratio'] for r in data if r[key] is not None]; ys = [r[key] for r in data if r[key] is not None]
                axes[row, col].plot(xs, ys, linewidth=2, markersize=7, label=label, **style[label])
            if supplied:
                axes[0, col].text(.5, .5, 'Domain glucose rises (boundary supply):\nthe domain total does not measure uptake',
                                  ha='center', va='center', transform=axes[0, col].transAxes, color='#555555')
        axes[0, col].set_title(model)
        for row in range(2):
            ax = axes[row, col]; ax.set_xscale('log'); ax.set_xticks([1, 2, 10, 100]); ax.set_xticklabels(['1', '2', '10', '100'])
            ax.grid(color='#e5e5e5', linewidth=.5); ax.set_axisbelow(True)
            for side in ('top', 'right'): ax.spines[side].set_visible(False)
        axes[1, col].set_xlabel('Intracellular dt / diffusion dt')
    axes[0, 0].set_ylabel('Glucose consumed (% of initial)'); axes[1, 0].set_ylabel('Biomass change (%)')
    axes[0, 0].legend(title='Build', frameon=False)
    fig.suptitle('Serial single-cell pilots, 10 simulated minutes, diffusion dt 0.01 min', fontsize=10)
    fig.tight_layout(); fig.savefig(out/'pilot_builds.png', dpi=180); fig.savefig(out/'pilot_builds.pdf'); plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after'):
        p.add_argument('--'+name, nargs=2, type=Path, required=True, metavar=('REPORT', 'CAMPAIGN'))
    p.add_argument('--labels', nargs=2, default=('before', 'after'))
    p.add_argument('--output', type=Path, required=True); p.add_argument('--plots', action='store_true')
    a = p.parse_args()
    records = load(*a.before, a.labels[0]) + load(*a.after, a.labels[1])
    reference = {(r['build'], r['model']): r for r in records if r['phase'] == 'timestep' and r['ratio'] == 1}
    for r in records:
        ref = reference.get((r['build'], r['model']))
        r['glucose_consumed_vs_ratio1'] = (r['glucose_consumed_percent']/ref['glucose_consumed_percent']
            if ref and r['glucose_consumed_percent'] is not None and ref['glucose_consumed_percent'] else None)
    traj = {label: defaultdict(dict) for label in a.labels}
    for (report, _), label in zip((a.before, a.after), a.labels):
        for t in rows(report/'tables/trajectories.csv'):
            if t['phase'] == 'timestep' and float(t['ratio']) == 1:
                traj[label][t['model']][t['time_minutes']] = (float(t['dry_mass_pg']), float(t['minimum_glucose_mM']), float(t['mean_glucose_mM']))
    ratio1 = {}
    for model in traj[a.labels[0]]:
        x, y = traj[a.labels[0]][model], traj[a.labels[1]].get(model, {})
        ratio1[model] = dict(samples=len(x), aligned=x.keys() == y.keys(),
            max_abs_difference=max((abs(u-v) for k in x if k in y for u, v in zip(x[k], y[k])), default=None))
    a.output.mkdir(parents=True, exist_ok=False); (a.output/'tables').mkdir()
    write_table(a.output/'tables/builds_by_ratio.csv', sorted(records, key=lambda r: (r['model'], r['phase'], r['ratio'], r['build'])))
    write_json(a.output/'comparison.json', dict(script_sha256=digest(__file__), labels=list(a.labels),
        reports={label: str(rep) for label, (rep, _) in zip(a.labels, (a.before, a.after))},
        report_analysis_sha256={label: digest(rep/'analysis.json') for label, (rep, _) in zip(a.labels, (a.before, a.after)) if (rep/'analysis.json').exists()},
        ratio1_trajectories_across_builds=ratio1,
        note='Exchange ledger: floating-point accounting tolerance from analyze_growth.exchange_ledger_pass. Ratio-1 trajectories compare dry mass, minimum and mean glucose at every after_cell_step sample.'))
    if a.plots:
        (a.output/'plots').mkdir(); plot(a.output/'plots', records, a.labels)
    for r in sorted(records, key=lambda r: (r['model'], r['phase'], r['ratio'], r['build'])):
        print(f"{r['model']:10s} {r['phase']:10s} ratio {r['ratio']:6g} {r['build']:8s} biomass {r['biomass_change_percent']:9.5f}%  "
              f"glucose used {r['glucose_consumed_percent'] if r['glucose_consumed_percent'] is not None else float('nan'):8.4f}%  "
              f"x ratio1 {r['glucose_consumed_vs_ratio1'] or float('nan'):6.2f}  ledger {'pass' if r['exchange_ledger_pass'] else 'FAIL'}  "
              f"min glc {r['minimum_glucose_mM']:.3e}  failures {r['solver_failures']}")
    print('ratio-1 trajectories across builds:', ratio1)


if __name__ == '__main__': main()
