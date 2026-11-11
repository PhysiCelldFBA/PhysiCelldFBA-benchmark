#!/usr/bin/env python3
"""Figures S1-S7 of the benchmark supplement, from the compact result tables in benchmarks/results/.

No simulations are run. Usage (inside a compute allocation, analysis environment active):
    python supplementary/make_figures.py
Writes supplementary/figures/FigS<n>.{pdf,png} and prints the values quoted in the text.
"""
import csv
from collections import defaultdict
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT/'benchmarks'/'results'
OUT = Path(__file__).resolve().parent/'figures'

# Categorical slots in fixed order (reference palette, light mode); text and grid tokens
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e3e2dc'
SEQ = ['#86b6ef', '#5598e7', '#2a78d6', '#256abf', '#1c5cab', '#104281']   # ordinal blue ramp (k = 2..100)
MARK = ['o', 's', '^', 'D', 'v', 'P', 'X', '*']

plt.rcParams.update({
    'font.size': 8, 'axes.titlesize': 8.5, 'axes.labelsize': 8, 'legend.fontsize': 7, 'xtick.labelsize': 7,
    'ytick.labelsize': 7, 'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2, 'ytick.color': INK2,
    'text.color': INK, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': GRID,
    'grid.linewidth': 0.6, 'lines.linewidth': 1.5, 'lines.markersize': 4.5, 'legend.frameon': False,
    'figure.dpi': 150, 'savefig.dpi': 300, 'savefig.bbox': 'tight', 'pdf.fonttype': 42,
})
NAMES = {'ecoli_core': 'E. coli core', 'mcf7_core': 'MCF7 core', 'iml1515': 'iML1515'}
MODELS = ('ecoli_core', 'mcf7_core', 'iml1515')


def rows(path):
    with open(path, newline='') as f:
        yield from csv.DictReader(f)


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return float('nan')


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    for ext in ('pdf', 'png'): fig.savefig(OUT/f'{name}.{ext}')
    plt.close(fig)


def panel_label(ax, s):
    ax.text(-0.14, 1.06, s, transform=ax.transAxes, fontweight='bold', fontsize=9, va='bottom')


# ---------------------------------------------------------------- S1 shared voxel and occupancy
def fig_s1():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    traj = defaultdict(list)
    for r in rows(RES/'voxel_sharing/voxel-final-20261102/tables/substrate_trajectories.csv'):
        if r['field_name'] == 'glucose' and r['phase'] in ('initial', 'after_cell_step'):
            traj[(int(r['threads']), r['order_seed'], r['repeat'])].append((num(r['time_minutes']), num(r['min_concentration'])))
    ax = axes[0]
    for t, color, ls, lw in ((1, C[0], '-', 3.0), (2, C[1], '--', 1.2), (4, C[2], ':', 1.2), (8, C[3], '-.', 1.2)):
        keys = [k for k in traj if k[0] == t]
        for i, k in enumerate(keys):
            x, y = zip(*sorted(traj[k]))
            ax.plot(x, y, color=color, ls=ls, lw=lw, alpha=0.9, label=f'{t} thread{"s" if t > 1 else ""} ({len(keys)} runs)' if i == 0 else None)
    ax.set(xlabel='Time (min)', ylabel='Minimum glucose (mM)', title='Eight cells in one 1.6 µm voxel')
    ax.legend(loc='upper right'); panel_label(ax, 'a')
    mesh = defaultdict(list)
    for r in rows(RES/'voxel_sharing/mesh-final-20261102/tables/substrate_trajectories.csv'):
        if r['field_name'] == 'glucose' and r['phase'] in ('initial', 'after_cell_step'):
            m = re.match(r'mesh(\d+)-', r['attempt']).group(1)
            mesh[(int(m), int(r['threads']), r['order_seed'], r['repeat'])].append((num(r['time_minutes']), num(r['min_concentration'])))
    ax = axes[1]
    for i, (m, occ) in enumerate(((16, 8), (8, 4), (4, 2), (2, 1))):
        for k in [k for k in mesh if k[0] == m]:
            x, y = zip(*sorted(mesh[k]))
            serial = k[1] == 1
            ax.plot(x, y, color=C[i], lw=3.0 if serial else 1.0, ls='-' if serial else '--', alpha=0.9 if serial else 0.6)
        ax.plot([], [], color=C[i], lw=2, label=f'{m} µm voxel, {occ} cell{"s" if occ > 1 else ""} per voxel')
    ax.plot([], [], color=INK2, lw=3.0, label='1 thread'); ax.plot([], [], color=INK2, lw=1.0, ls='--', label='2, 4, 8 threads')
    ax.set(xlabel='Time (min)', ylabel='Minimum glucose (mM)', title='Eight separated cells, four meshes')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=6.5); panel_label(ax, 'b')
    fig.tight_layout(); save(fig, 'FigS1')


# ---------------------------------------------------------------- S2/S3 timestep accuracy
def accuracy_runs():
    out = []
    for tag, dt in (('d0_01', 0.01), ('d0_001', 0.001)):
        for r in rows(RES/f'timestep/tradeoff-accuracy-{tag}-final-20261102/tables/runs.csv'):
            if not r['build'].startswith('pr-') or abs(num(r['diffusion_dt_minutes']) - dt) > 1e-12: continue
            r['dt'] = dt; r['k'] = int(r['ratio'])
            # ring marker: any LP update not solved to optimality (concentration flags are reported in the tables)
            r['ok'] = num(r['solver_failures']) == 0 and num(r['nonoptimal_updates']) == 0
            out.append(r)
    return out


def fig_s2(runs):
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.2), sharex=True)
    floor = 1e-12
    for col, dt in enumerate((0.01, 0.001)):
        for row, (key, lab) in enumerate((('max_biomass_rel_error', 'Max |relative biomass error|'), ('glucose_uptake_rel_error', '|Relative glucose uptake error|'))):
            ax = axes[row, col]
            for i, sc in enumerate(('A1', 'A2', 'A3', 'A4')):
                pts = sorted((r['k'], max(abs(num(r[key])), floor), r['ok']) for r in runs if r['dt'] == dt and r['scenario'] == sc and r['k'] > 1)
                ks, ys, ok = zip(*pts)
                a3 = sc == 'A3'   # A3 and A4 coincide where neither is limited by its voxel: draw A3 open, larger, dashed
                ax.plot(ks, ys, color=C[i], marker=MARK[i], label=sc, mfc='white' if a3 else C[i], ms=7 if a3 else 4.5, ls='--' if a3 else '-', zorder=3 if a3 else 2)
                bad = [(k, y) for k, y, o in pts if not o]
                if bad: ax.plot(*zip(*bad), ls='none', marker='o', ms=10, mfc='none', mec=INK, mew=1.0, label='LP not optimal' if i == 2 else None)
            ax.set(xscale='log', yscale='log', ylabel=lab)
            ax.set_xticks([2, 5, 10, 20, 50, 100]); ax.set_xticklabels(['2', '5', '10', '20', '50', '100'])
            if row == 0: ax.set_title(f'Diffusion dt = {dt:g} min')
            if row == 1: ax.set_xlabel('k = intracellular dt / diffusion dt')
            panel_label(ax, 'abcd'[row*2+col])
    h, l = axes[0, 0].get_legend_handles_labels()
    order = [l.index(x) for x in ('A1', 'A2', 'A3', 'A4', 'LP not optimal') if x in l]
    h, l = [h[i] for i in order], [l[i] for i in order]
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.legend(h, l, loc='upper center', ncol=5, bbox_to_anchor=(0.5, 1.0)); save(fig, 'FigS2')


def fig_s3(runs):
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.3), sharey=True)
    for i, sc in enumerate(('A1', 'A2', 'A3', 'A4')):
        ax = axes[i]
        for j, dt in enumerate((0.01, 0.001)):
            pts = sorted((num(r['intracellular_dt_minutes']), max(abs(num(r['max_biomass_rel_error'])), 1e-10), r['ok']) for r in runs if r['dt'] == dt and r['scenario'] == sc and r['k'] > 1)
            x, y, ok = zip(*pts)
            ax.plot(x, y, color=C[j], marker=MARK[j], ls='-' if j == 0 else '--', label=f'diffusion dt {dt:g} min')
            bad = [(a, b) for a, b, o in pts if not o]
            if bad: ax.plot(*zip(*bad), ls='none', marker='o', ms=10, mfc='none', mec=INK, mew=1.0)
        ax.set(xscale='log', yscale='log', title=sc, xlabel='Intracellular dt (min)')
        if i == 0: ax.set_ylabel('Max |relative biomass error|')
    axes[0].legend(loc='lower right', fontsize=6)
    fig.tight_layout(); save(fig, 'FigS3')


# ---------------------------------------------------------------- S4 timestep cost
def fig_s4():
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=True)
    data = defaultdict(dict)
    for tag, dt in (('d0_01', 0.01), ('d0_001', 0.001)):
        for r in rows(RES/f'timestep/tradeoff-cost-{tag}-final-20261102/tables/summary.csv'):
            data[(r['model'], int(r['threads']), dt)][int(r['ratio'])] = num(r['loop_speedup_vs_k1'])
    for i, m in enumerate(MODELS):
        ax = axes[i]
        ks = np.array([1, 2, 5, 10, 20, 50, 100])
        ax.plot(ks, ks, color=INK2, lw=0.8, ls=':', label='speed-up = k')
        for j, (t, dt) in enumerate(((1, 0.01), (1, 0.001), (56, 0.01), (56, 0.001))):
            d = data[(m, t, dt)]
            ax.plot(sorted(d), [d[k] for k in sorted(d)], color=C[0] if t == 1 else C[1], ls='-' if dt == 0.01 else '--',
                    marker=MARK[0] if t == 1 else MARK[1], mfc='white' if dt == 0.001 else None,
                    label=f'{t} thread{"s" if t > 1 else ""}, diffusion dt {dt:g}')
        ax.set(xscale='log', yscale='log', title=NAMES[m], xlabel='k = intracellular dt / diffusion dt')
        ax.set_xticks([1, 2, 5, 10, 20, 50, 100]); ax.set_xticklabels(['1', '2', '5', '10', '20', '50', '100'])
        if i == 0: ax.set_ylabel('Simulation-loop speed-up vs k = 1')
    axes[0].legend(loc='upper left', fontsize=6)
    fig.tight_layout(); save(fig, 'FigS4')


# ---------------------------------------------------------------- S5 growth controls
def fig_s5():
    series = defaultdict(list)
    for r in rows(RES/'growth_conditions/growth-final-20261102/tables/biomass.csv'):
        series[r['case_id']].append((num(r['time_minutes']), num(r['biomass_change_percent'])))
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5))
    panels = (('E. coli core, fed colony medium', 'ecoli_colony_fed', None), ('iML1515, fed medium', 'iml_fed', 'iml_batch'),
              ('MCF7 core, native gradient medium', 'mcf7_native', None))
    for i, (title, prof, extra) in enumerate(panels):
        ax = axes[i]
        for j, dt in enumerate(('0_01', '0_1', '1')):
            cid = f'growth-{prof}-dfba-n1-fixed0-dt{dt}'
            x, y = zip(*sorted(series[cid]))
            ax.plot(x, y, color=C[j], ls=('-', '--', ':')[j], label=f'intracellular dt {dt.replace("_", ".")} min')
        if extra:
            x, y = zip(*sorted(series[f'growth-{extra}-dfba-n1-fixed0-dt0_01']))
            ax.plot(x, y, color=C[3], lw=1.0, ls='-.', label='batch medium, dt 0.01 min')
        if prof == 'mcf7_native':
            x, y = zip(*sorted(series['growth-mcf7_native-pfba-n1-fixed0-dt0_01']))
            ax.plot(x, y, color=C[4], lw=1.0, ls='-.', label='pFBA, dt 0.01 min')
        ax.set(title=title, xlabel='Time (min)')
        if i == 0: ax.set_ylabel('Dry-mass change (%)')
        ax.legend(loc='upper left', fontsize=6)
        panel_label(ax, 'abc'[i])
    fig.tight_layout(); save(fig, 'FigS5')


# ---------------------------------------------------------------- S6 FBA vs pFBA
def fig_s6():
    single = list(rows(RES/'pfba/pfba-final-20261104/tables/single_runs.csv'))
    traj = defaultdict(list)
    for r in rows(RES/'pfba/pfba-final-20261104/tables/application_trajectories.csv'):
        traj[(r['variant'], num(r['intracellular_dt']))].append(r)
    fig = plt.figure(figsize=(7.2, 5.0))
    gs = fig.add_gridspec(2, 3)
    ax = fig.add_subplot(gs[0, 0])
    ref = {r['variant']: r for r in single if abs(num(r['intracellular_dt']) - 0.01) < 1e-9}
    labels = ['Glucose\nuptake', 'O₂\nuptake', 'Lactate\nsecretion']
    keys = ['mean_net_export_D-Glucose', 'mean_net_export_O2', 'mean_net_export_L-Lactate']
    x = np.arange(3); w = 0.36
    for j, v in enumerate(('dfba', 'pfba')):
        vals = [abs(num(ref[v][k])) for k in keys]
        ax.bar(x + (j-0.5)*w, vals, w*0.92, color=C[j], label='FBA' if v == 'dfba' else 'pFBA')
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel('|Mean net exchange| (BioFVM units/min)')
    ax.set_title('Single cell, exchange rates'); ax.legend(loc='upper right'); ax.grid(axis='x', visible=False)
    panel_label(ax, 'a')
    ax = fig.add_subplot(gs[0, 1])
    for j, v in enumerate(('dfba', 'pfba')):
        ax.bar(j, num(ref[v]['median_internal_abs_flux']), 0.6, color=C[j])
    ax.set(yscale='log', ylabel='Median total internal |flux|', title='Single cell, internal flux')
    ax.set_xticks([0, 1]); ax.set_xticklabels(['FBA', 'pFBA']); ax.grid(axis='x', visible=False)
    panel_label(ax, 'b')
    specs = (('live_cells', 'Live cells', 1), ('live_dry_mass_pg', 'Live dry mass (10⁵ pg)', 1e-5),
             ('mean_L-Lactate_mM', 'Mean lactate (mM)', 1), ('mean_O2_mM', 'Mean O₂ (mM)', 1))
    pos = [gs[0, 2], gs[1, 0], gs[1, 1], gs[1, 2]]
    for p, (key, lab, scale) in enumerate(specs):
        ax = fig.add_subplot(pos[p])
        for j, v in enumerate(('dfba', 'pfba')):
            for dt, ls in ((0.01, '-'), (0.1, '--')):
                rs = sorted(traj[(v, dt)], key=lambda r: num(r['time_minutes']))
                ax.plot([num(r['time_minutes'])/60 for r in rs], [num(r[key])*scale for r in rs], color=C[j], ls=ls, lw=1.3,
                        label=f'{"FBA" if v == "dfba" else "pFBA"}, dt {dt:g} min')
        ax.set(xlabel='Time (h)', ylabel=lab, title='Application'); ax.set_xticks([0, 24, 48, 72])
        if p == 0: ax.legend(loc='upper right', fontsize=6)
        panel_label(ax, 'cdef'[p])
    fig.tight_layout(); save(fig, 'FigS6')


# ---------------------------------------------------------------- S7 performance and scaling
def fig_s7():
    S = list(rows(RES/'performance/scaling-final-20261104/tables/summary.csv'))
    def get(**kw):
        return [r for r in S if all(str(r[k]) == str(v) for k, v in kw.items())]
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.0))
    # a: microseconds per cell-step vs cells
    ax = axes[0, 0]
    for i, m in enumerate(MODELS):
        for t, ls in (('1', '-'), ('56', '--')):
            rs = sorted(get(model=m, variant='dfba', threads=t, fields=23), key=lambda r: int(r['cells']))
            ax.plot([int(r['cells']) for r in rs], [num(r['microseconds_per_cell_step']) for r in rs], color=C[i], ls=ls, marker=MARK[i],
                    mfc='white' if t == '56' else None, label=f'{NAMES[m]}, {t} thread{"s" if t != "1" else ""}')
    ax.set(xscale='log', yscale='log', xlabel='Cells', ylabel='Loop time per cell and step (µs)', title='Cost per cell-step')
    panel_label(ax, 'a')
    # b: speed-up vs threads at 1000 cells
    ax = axes[0, 1]
    th = [1, 2, 4, 8, 16, 28, 56, 112]
    ax.plot(th, th, color=INK2, lw=0.8, ls=':', label='ideal')
    for i, m in enumerate(MODELS):
        rs = sorted(get(model=m, variant='dfba', cells=1000, fields=23), key=lambda r: int(r['threads']))
        ax.plot([int(r['threads']) for r in rs], [num(r['speedup_vs_1_thread']) for r in rs], color=C[i], marker=MARK[i], label='_' + NAMES[m])
    for i, (v, lab) in enumerate((('dfba_disabled', 'no metabolism'), ('upstream_physicell', 'PhysiCell'))):
        rs = sorted(get(model='mcf7_core', variant=v, cells=1000, fields=23), key=lambda r: int(r['threads']))
        ax.plot([int(r['threads']) for r in rs], [num(r['speedup_vs_1_thread']) for r in rs], color=INK2, lw=1.0, ls=('--', '-.')[i], label=f'MCF7 workload, {lab}')
    ax.set(xscale='log', yscale='log', xlabel='Threads', ylabel='Speed-up vs 1 thread', title='Strong scaling, 1000 cells')
    ax.set_xticks(th); ax.set_xticklabels([str(t) for t in th]); ax.legend(fontsize=5.5, loc='upper left'); panel_label(ax, 'b')
    # c: loop time of the three variants vs threads (MCF7 core workload, 1000 cells)
    ax = axes[0, 2]
    for i, (v, lab) in enumerate((('dfba', 'PhysiCelldFBA'), ('dfba_disabled', 'PhysiCelldFBA, no metabolism'), ('upstream_physicell', 'PhysiCell'))):
        for j, m in enumerate(MODELS):
            rs = sorted(get(model=m, variant=v, cells=1000, fields=23), key=lambda r: int(r['threads']))
            ax.plot([int(r['threads']) for r in rs], [num(r['loop_seconds']) for r in rs], color=C[j], ls=('-', '--', ':')[i], lw=1.2,
                    marker=MARK[j] if i == 0 else None)
    ax.plot([], [], color=INK2, ls='-', label='PhysiCelldFBA'); ax.plot([], [], color=INK2, ls='--', label='no metabolism'); ax.plot([], [], color=INK2, ls=':', label='PhysiCell')
    ax.set(xscale='log', yscale='log', xlabel='Threads', ylabel='Simulation-loop time (s)', title='Loop time, 1000 cells, 10 min')
    ax.set_xticks(th); ax.set_xticklabels([str(t) for t in th], fontsize=6); ax.legend(fontsize=5.5, loc='upper right'); panel_label(ax, 'c')
    # d: overhead ratio, no metabolism / PhysiCell, all points
    ax = axes[1, 0]
    for i, m in enumerate(MODELS):
        rs = [r for r in get(model=m, variant='dfba_disabled') if r['loop_ratio_vs_upstream_physicell']]
        ax.scatter([int(r['threads']) * (1 + 0.06*(i-1)) for r in rs], [num(r['loop_ratio_vs_upstream_physicell']) for r in rs], s=12,
                   color=C[i], marker=MARK[i], label=NAMES[m], edgecolors='white', linewidths=0.4)
    ax.axhline(1, color=INK2, lw=0.8)
    ax.set(xscale='log', ylim=(0.8, 1.2), xlabel='Threads', ylabel='Loop time ratio\n(no metabolism / PhysiCell)', title='Overhead, no metabolism')
    ax.set_xticks(th); ax.set_xticklabels([str(t) for t in th], fontsize=6); panel_label(ax, 'd')
    # e: fields
    ax = axes[1, 1]
    for i, m in enumerate(MODELS):
        rs = sorted(get(model=m, variant='dfba', cells=1000, threads=56), key=lambda r: int(r['fields']))
        ax.plot([int(r['fields']) for r in rs], [num(r['loop_seconds']) for r in rs], color=C[i], marker=MARK[i], label=NAMES[m])
    ax.set(yscale='log', xlabel='Diffusing fields', ylabel='Simulation-loop time (s)', title='Fields, 1000 cells, 56 threads')
    panel_label(ax, 'e')
    # f: memory
    ax = axes[1, 2]
    for i, m in enumerate(MODELS):
        rs = sorted(get(model=m, variant='dfba', threads=56, fields=23), key=lambda r: int(r['cells']))
        ax.plot([int(r['cells']) for r in rs], [num(r['peak_rss_gib']) for r in rs], color=C[i], marker=MARK[i], label=NAMES[m])
    ax.set(xscale='log', yscale='log', xlabel='Cells', ylabel='Peak memory (GiB)', title='Memory, 56 threads')
    panel_label(ax, 'f')
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=C[i], marker=MARK[i], label=NAMES[m]) for i, m in enumerate(MODELS)]
    handles += [Line2D([], [], color=INK2, ls='-', marker='o', label='1 thread (a)'),
                Line2D([], [], color=INK2, ls='--', marker='o', mfc='white', label='56 threads (a)')]
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.legend(handles=handles, loc='upper center', ncol=5, bbox_to_anchor=(0.5, 1.0)); save(fig, 'FigS7')


def main():
    runs = accuracy_runs()
    fig_s1(); fig_s2(runs); fig_s3(runs); fig_s4(); fig_s5(); fig_s6(); fig_s7()
    print('accuracy runs (PhysiCelldFBA build):', len(runs))
    for r in sorted(runs, key=lambda r: (r['dt'], r['scenario'], r['k'])):
        print(f"dt={r['dt']:g} {r['scenario']} k={r['k']:3d} final={num(r['final_biomass_rel_error']):+.3g} max={num(r['max_biomass_rel_error']):.3g} "
              f"glc={num(r['glucose_uptake_rel_error']):+.3g} o2={num(r['oxygen_uptake_rel_error']):+.3g} gmin={num(r['glucose_min_mM']):.3g} "
              f"o2min={num(r['oxygen_min_mM']):.3g} ok={r['ok']} fail={r['solver_failures']} nonopt={r['nonoptimal_updates']} ledger={r['exchange_ledger_pass']} updates={r['updates']}")
    print('figures written to', OUT)


if __name__ == '__main__': main()
