#!/usr/bin/env python3
"""Analyze the performance/scaling campaign (prepare_final_studies.py --stage scaling); no simulations or submissions.

Medians over repeats of the simulation-loop time and its split, per model, variant, cells, threads and fields:
  - strong scaling at 1000 cells: speed-up and parallel efficiency against 1 thread;
  - size: loop time per cell and step for 100/1000/10000 cells at 1 and 56 threads;
  - variants: PhysiCelldFBA with metabolism against without metabolism and against upstream PhysiCell;
  - fields at 1000 cells and 56 threads.
Every attempt is retained; flagged runs and thread mismatches are counted, not dropped.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import statistics
from common import digest, read_json, write_json

PARTS = ('intracellular_seconds', 'diffusion_seconds', 'exchange_seconds', 'mechanics_seconds', 'phenotype_seconds', 'output_seconds')
VARIANTS = ('dfba', 'dfba_disabled', 'upstream_physicell')
LABELS = {'dfba': 'PhysiCelldFBA', 'dfba_disabled': 'PhysiCelldFBA, no metabolism', 'upstream_physicell': 'upstream PhysiCell'}
STEPS = 1001   # 10 simulated minutes at diffusion dt 0.01; the loop also runs at t = 10


def write_table(path, records):
    keys = list(dict.fromkeys(k for r in records for k in r))
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator='\n'); writer.writeheader(); writer.writerows(records)


def inspect(run):
    case = read_json(run/'manifest.json')['case']; metrics = read_json(run/'metrics.json')
    t = read_json(run/'inputs/benchmark_metrics.json') if (run/'inputs/benchmark_metrics.json').exists() else {}
    r = dict(model=case['model'], variant=case['variant'], cells=case['cells_requested'], threads=case['threads'], fields=case['fields'],
             repeat=case['repeat'], status=metrics['status'], flags=';'.join(t.get('diagnostic_flags', [])),
             actual_threads=t.get('actual_threads'), final_cells=t.get('final_cells'), updates=t.get('intracellular_updates'),
             solver_failures=t.get('solver_failures'), wall_seconds=metrics.get('resource', {}).get('elapsed_seconds'),
             peak_rss_kib=metrics.get('resource', {}).get('peak_rss_kib'), loop_seconds=t.get('simulation_loop_seconds'),
             initialization_seconds=t.get('initialization_seconds'), attempt=run.name, case_id=case['case_id'])
    for p in PARTS: r[p] = t.get(p)
    return r


def summarize(records):
    groups = defaultdict(list)
    for r in records: groups[(r['model'], r['variant'], r['cells'], r['threads'], r['fields'])].append(r)
    med = lambda g, k: statistics.median(x[k] for x in g) if g and all(x[k] is not None for x in g) else None
    out = []
    for (model, variant, cells, threads, fields), g in sorted(groups.items()):
        s = dict(model=model, variant=variant, cells=cells, threads=threads, fields=fields, runs=len(g),
                 flagged=sum(bool(x['flags']) for x in g), thread_mismatches=sum(x['actual_threads'] != threads for x in g),
                 incomplete=sum(x['status'] not in ('completed', 'completed_flagged') for x in g),
                 loop_seconds=med(g, 'loop_seconds'), wall_seconds=med(g, 'wall_seconds'), peak_rss_gib=(med(g, 'peak_rss_kib') or 0)/1048576,
                 loop_spread=(max(x['loop_seconds'] for x in g)-min(x['loop_seconds'] for x in g))/med(g, 'loop_seconds') if med(g, 'loop_seconds') else None)
        for p in PARTS: s[p] = med(g, p)
        s['microseconds_per_cell_step'] = 1e6*s['loop_seconds']/(cells*STEPS) if s['loop_seconds'] else None
        out.append(s)
    index = {(s['model'], s['variant'], s['cells'], s['threads'], s['fields']): s for s in out}
    # The cell and thread sweeps share one field count per model (the most frequent); the field sweep varies it.
    ref_fields = {m: Counter(s['fields'] for s in out if s['model'] == m).most_common(1)[0][0] for m in {s['model'] for s in out}}
    for s in out:
        one = index.get((s['model'], s['variant'], s['cells'], 1, s['fields']))
        if one and s['loop_seconds'] and one['loop_seconds']:
            s['speedup_vs_1_thread'] = one['loop_seconds']/s['loop_seconds']; s['parallel_efficiency'] = s['speedup_vs_1_thread']/s['threads']
        for other in ('dfba_disabled', 'upstream_physicell'):
            o = index.get((s['model'], other, s['cells'], s['threads'], s['fields']))
            if s['variant'] == 'dfba' and o and o['loop_seconds']: s[f'loop_ratio_vs_{other}'] = s['loop_seconds']/o['loop_seconds']
        u = index.get((s['model'], 'upstream_physicell', s['cells'], s['threads'], s['fields']))
        if s['variant'] == 'dfba_disabled' and u and u['loop_seconds']: s['loop_ratio_vs_upstream_physicell'] = s['loop_seconds']/u['loop_seconds']
        s['reference_fields'] = s['fields'] == ref_fields[s['model']]
    return out


def plot(out, summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    models = sorted({s['model'] for s in summary})
    style = {'dfba': dict(color='#2a78d6', marker='o'), 'dfba_disabled': dict(color='#eb6834', marker='s'), 'upstream_physicell': dict(color='#1baf7a', marker='^')}
    def finish(fig, name, title):
        fig.suptitle(title, fontsize=9); fig.tight_layout(); fig.savefig(out/f'{name}.png', dpi=160); fig.savefig(out/f'{name}.pdf'); plt.close(fig)
    def axes_style(ax):
        ax.grid(color='#e5e5e5', linewidth=.5)
        for side in ('top', 'right'): ax.spines[side].set_visible(False)
    # strong scaling at 1000 cells, reference fields
    fig, axes = plt.subplots(1, len(models), figsize=(4.4*len(models), 4), squeeze=False)
    for ax, m in zip(axes[0], models):
        for v in VARIANTS:
            d = sorted((s for s in summary if s['model'] == m and s['variant'] == v and s['cells'] == 1000 and s['reference_fields'] and s.get('speedup_vs_1_thread')), key=lambda s: s['threads'])
            if d: ax.plot([s['threads'] for s in d], [s['speedup_vs_1_thread'] for s in d], linewidth=2, markersize=6, label=LABELS[v], **style[v])
        ts = sorted({s['threads'] for s in summary})
        ax.plot(ts, ts, '--', color='#888888', linewidth=1, label='ideal')
        ax.set(xscale='log', yscale='log', title=m, xlabel='OpenMP threads'); ax.set_xticks(ts); ax.set_xticklabels([str(t) for t in ts]); axes_style(ax)
    axes[0, 0].set_ylabel('Simulation-loop speed-up vs 1 thread'); axes[0, 0].legend(frameon=False, fontsize=8)
    finish(fig, 'strong_scaling', '1000 cells, 10 simulated minutes, k = 1, diffusion dt 0.01 min, median of 3 repeats')
    # size: loop time against cells at 1 and 56 threads
    fig, axes = plt.subplots(1, len(models), figsize=(4.4*len(models), 4), squeeze=False)
    for ax, m in zip(axes[0], models):
        for v in VARIANTS:
            for p, ls in ((1, '-'), (56, ':')):
                d = sorted((s for s in summary if s['model'] == m and s['variant'] == v and s['threads'] == p and s['reference_fields'] and s['loop_seconds']), key=lambda s: s['cells'])
                if len(d) > 1: ax.plot([s['cells'] for s in d], [s['loop_seconds'] for s in d], linestyle=ls, linewidth=2, markersize=6, label=f"{LABELS[v]}, {p} thr", **style[v])
        ax.set(xscale='log', yscale='log', title=m, xlabel='Cells'); ax.set_xticks([100, 1000, 10000]); ax.set_xticklabels(['100', '1000', '10000']); axes_style(ax)
    axes[0, 0].set_ylabel('Simulation-loop time (s)'); axes[0, 0].legend(frameon=False, fontsize=7)
    finish(fig, 'cells', 'Loop time against cell count; solid: 1 thread, dotted: 56 threads')
    # fields at 1000 cells, 56 threads
    fig, axes = plt.subplots(1, len(models), figsize=(4.4*len(models), 4), squeeze=False)
    for ax, m in zip(axes[0], models):
        for v in VARIANTS:
            d = sorted((s for s in summary if s['model'] == m and s['variant'] == v and s['cells'] == 1000 and s['threads'] == 56 and s['loop_seconds']), key=lambda s: s['fields'])
            if d: ax.plot([s['fields'] for s in d], [s['loop_seconds'] for s in d], linewidth=2, markersize=6, label=LABELS[v], **style[v])
        ax.set(yscale='log', title=m, xlabel='Fields (substrates)'); axes_style(ax)
    axes[0, 0].set_ylabel('Simulation-loop time (s)'); axes[0, 0].legend(frameon=False, fontsize=8)
    finish(fig, 'fields', '1000 cells, 56 threads')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--plots', action='store_true'); p.add_argument('--partial', action='store_true', help='Allow missing cases (testing only)')
    a = p.parse_args()
    expected = {json.loads(l)['case_id'] for l in (a.campaign/'timestep/cases.jsonl').read_text().splitlines()}
    runs = sorted(q.parent for q in (a.campaign/'timestep/runs').glob('*/manifest.json'))
    records = [inspect(r) for r in runs]
    seen = [r['case_id'] for r in records]
    if not a.partial and sorted(seen) != sorted(expected): raise ValueError('Missing, duplicated or unexpected attempts')
    summary = summarize(records)
    a.output.mkdir(parents=True, exist_ok=False); (a.output/'tables').mkdir(); (a.output/'data').mkdir()
    copied = {}
    for run in runs:
        dest = a.output/'data'/run.name; dest.mkdir()
        for f in [run/n for n in ('manifest.json', 'metrics.json', 'hardware.json', 'stdout.log', 'stderr.log', 'resource.tsv')] + [run/'inputs/benchmark_metrics.json', run/'inputs/settings.xml']:
            if f.exists(): (dest/f.name).write_bytes(f.read_bytes()); copied[str((dest/f.name).relative_to(a.output))] = digest(f)
    write_table(a.output/'tables/runs.csv', sorted(records, key=lambda r: (r['model'], r['variant'], r['cells'], r['threads'], r['fields'], r['repeat'])))
    write_table(a.output/'tables/summary.csv', summary)
    write_json(a.output/'analysis.json', dict(script_sha256=digest(__file__), campaign=str(a.campaign.resolve()), attempts=len(records),
        expected_cases=len(expected), missing=sorted(expected-set(seen)), evidence_sha256=copied))
    if a.plots: (a.output/'plots').mkdir(); plot(a.output/'plots', summary)
    for s in summary:
        print(f"{s['model']:10s} {s['variant']:18s} n{s['cells']:<5} p{s['threads']:<3} f{s['fields']:<2} runs={s['runs']} flagged={s['flagged']} "
              f"loop={s['loop_seconds'] or float('nan'):10.3f}s speedup={s.get('speedup_vs_1_thread') or float('nan'):6.2f} "
              f"vs_off={s.get('loop_ratio_vs_dfba_disabled') or float('nan'):8.2f} vs_up={s.get('loop_ratio_vs_upstream_physicell') or float('nan'):8.2f}")


if __name__ == '__main__': main()
