#!/usr/bin/env python3
"""Analyze timestep trade-off cost campaigns (prepare_tradeoff.py --stage cost-pilot/cost).

Reads per-run telemetry (minimal output). For each model, thread count and k it reports
the median over repeats of the simulation-loop time and its split, and the speed-up over
k = 1 at the same model and thread count. The Amdahl bound loop / (loop - intracellular)
at k = 1 is the most any k can save. No simulations or submissions.
"""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
import statistics
from common import digest, read_json, write_json

PARTS = ('intracellular_seconds', 'diffusion_seconds', 'exchange_seconds', 'mechanics_seconds', 'phenotype_seconds', 'output_seconds')


def write_table(path, records):
    keys = list(dict.fromkeys(k for r in records for k in r))
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator='\n'); writer.writeheader(); writer.writerows(records)


def inspect(run):
    case = read_json(run/'manifest.json')['case']; metrics = read_json(run/'metrics.json')
    t = read_json(run/'inputs/benchmark_metrics.json') if (run/'inputs/benchmark_metrics.json').exists() else {}
    r = dict(model=case['model'], threads=case['threads'], ratio=case['ratio'], repeat=case['repeat'], status=metrics['status'],
             flags=';'.join(t.get('diagnostic_flags', [])), actual_threads=t.get('actual_threads'),
             cells=t.get('final_cells'), updates=t.get('intracellular_updates'), solver_failures=t.get('solver_failures'),
             wall_seconds=metrics.get('resource', {}).get('elapsed_seconds'), loop_seconds=t.get('simulation_loop_seconds'),
             solver_thread_seconds=t.get('solver_thread_seconds'), attempt=run.name, case_id=case['case_id'])
    for p in PARTS: r[p] = t.get(p)
    return r


def summarize(records):
    groups = defaultdict(list)
    for r in records: groups[(r['model'], r['threads'], r['ratio'])].append(r)
    med = lambda g, k: statistics.median(x[k] for x in g) if all(x[k] is not None for x in g) else None
    out = []
    for (model, threads, k), g in sorted(groups.items()):
        s = dict(model=model, threads=threads, ratio=k, runs=len(g), flagged=sum(bool(x['flags']) for x in g),
                 thread_mismatches=sum(x['actual_threads'] != threads for x in g), updates=med(g, 'updates'),
                 loop_seconds=med(g, 'loop_seconds'), wall_seconds=med(g, 'wall_seconds'),
                 loop_range_seconds=max(x['loop_seconds'] for x in g)-min(x['loop_seconds'] for x in g))
        for p in PARTS: s[p] = med(g, p)
        out.append(s)
    ref = {(s['model'], s['threads']): s for s in out if s['ratio'] == 1}
    for s in out:
        b = ref.get((s['model'], s['threads']))
        s['loop_speedup_vs_k1'] = b['loop_seconds']/s['loop_seconds'] if b and s['loop_seconds'] else None
        s['intracellular_share_at_k1'] = b['intracellular_seconds']/b['loop_seconds'] if b else None
        s['amdahl_bound'] = b['loop_seconds']/(b['loop_seconds']-b['intracellular_seconds']) if b and b['loop_seconds'] > b['intracellular_seconds'] else None
    return out


def plot(out, summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    models = sorted({s['model'] for s in summary})
    style = {1: dict(color='#2a78d6', marker='o'), 56: dict(color='#eb6834', marker='s')}
    fig, axes = plt.subplots(1, len(models), figsize=(4.4*len(models), 4), squeeze=False)
    for ax, model in zip(axes[0], models):
        for threads in sorted({s['threads'] for s in summary}):
            data = sorted((s for s in summary if s['model'] == model and s['threads'] == threads), key=lambda s: s['ratio'])
            ax.plot([s['ratio'] for s in data], [s['loop_speedup_vs_k1'] for s in data], linewidth=2, markersize=6,
                    label=f'{threads} thread{"s" if threads > 1 else ""}', **style.get(threads, {}))
            bound = data[0]['amdahl_bound'] if data else None
            if bound: ax.axhline(bound, color=style.get(threads, {}).get('color', 'grey'), linestyle=':', linewidth=1)
        ks = sorted({s['ratio'] for s in summary})
        ax.plot(ks, ks, color='#888888', linewidth=1, linestyle='--', label='k (all time in LPs)')
        ax.set(xscale='log', yscale='log', title=model, xlabel='k = intracellular dt / diffusion dt')
        ax.set_xticks(ks); ax.set_xticklabels([str(k) for k in ks]); ax.grid(color='#e5e5e5', linewidth=.5)
        for side in ('top', 'right'): ax.spines[side].set_visible(False)
    axes[0, 0].set_ylabel('Simulation-loop speed-up vs k = 1'); axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle('1000 cells, 10 simulated minutes, minimal output; dotted: Amdahl bound from the k = 1 intracellular share', fontsize=9)
    fig.tight_layout(); fig.savefig(out/'cost.png', dpi=160); fig.savefig(out/'cost.pdf'); plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--plots', action='store_true')
    a = p.parse_args()
    import json
    expected = {json.loads(l)['case_id'] for l in (a.campaign/'timestep/cases.jsonl').read_text().splitlines()}
    runs = sorted(q.parent for q in (a.campaign/'timestep/runs').glob('*/manifest.json'))
    records = [inspect(r) for r in runs]
    if sorted(r['case_id'] for r in records) != sorted(expected): raise ValueError('Missing, duplicated or unexpected attempts')
    summary = summarize(records)
    a.output.mkdir(parents=True, exist_ok=False); (a.output/'tables').mkdir(); (a.output/'data').mkdir()
    copied = {}
    for run in runs:
        dest = a.output/'data'/run.name; dest.mkdir()
        for f in [run/n for n in ('manifest.json', 'metrics.json', 'hardware.json', 'stdout.log', 'stderr.log', 'resource.tsv')] + [run/'inputs/benchmark_metrics.json', run/'inputs/settings.xml']:
            if f.exists(): (dest/f.name).write_bytes(f.read_bytes()); copied[str((dest/f.name).relative_to(a.output))] = digest(f)
    write_table(a.output/'tables/runs.csv', sorted(records, key=lambda r: (r['model'], r['threads'], r['ratio'], r['repeat'])))
    write_table(a.output/'tables/summary.csv', summary)
    write_json(a.output/'analysis.json', dict(script_sha256=digest(__file__), campaign=str(a.campaign.resolve()), attempts=len(records), evidence_sha256=copied))
    if a.plots: (a.output/'plots').mkdir(); plot(a.output/'plots', summary)
    for s in summary:
        print(f"{s['model']:10s} p{s['threads']:<3d} k={s['ratio']:<4} loop {s['loop_seconds']:9.2f}s  intra {s['intracellular_seconds']:9.2f}s  diff {s['diffusion_seconds']:7.2f}s  "
              f"speedup {s['loop_speedup_vs_k1']:6.2f}  amdahl {s['amdahl_bound'] or float('nan'):6.2f}  flagged {s['flagged']}  thread mismatch {s['thread_mismatches']}")


if __name__ == '__main__': main()
