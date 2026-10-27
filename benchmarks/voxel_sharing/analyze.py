#!/usr/bin/env python3
"""Manually summarize the shared-voxel campaign, retaining flagged/failed attempts.

Reads compact CSV telemetry; use pctk for additional MultiCellDS variables.
Writes a new, publication-oriented report with tables, optional plots and evidence.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'performance'))
from common import digest, read_json, write_json


def rows(path):
    if not path.is_file(): return []
    with path.open() as stream: return list(csv.DictReader(stream))


def number(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError): return None


def write_table(path, records):
    keys=sorted({k for record in records for k in record})
    with path.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys); writer.writeheader(); writer.writerows(records)


def inspect_run(run):
    manifest=read_json(run/'manifest.json'); case=manifest['case']
    metrics=read_json(run/'metrics.json') if (run/'metrics.json').exists() else {'status':'missing_metrics'}
    telemetry=metrics.get('telemetry') or {}
    updates=rows(run/'inputs/benchmark_update_counts.csv')
    population=rows(run/'inputs/benchmark_population.csv')
    final=next((r for r in reversed(population) if r['phase']=='final'),{})
    order=run/'inputs/benchmark_order.csv'
    record=dict(attempt=run.name,case_id=case['case_id'],threads=case['threads'],
        mesh_id=case.get('mesh_id','original'),voxel_size_um=case.get('voxel_size_um'),
        expected_max_occupancy=case.get('expected_max_occupancy'),
        order_seed=case['order_seed'],repeat=case['repeat'],status=metrics['status'],
        flags=';'.join(telemetry.get('diagnostic_flags',[])),
        initial_cells=telemetry.get('initial_cells'),final_cells=telemetry.get('final_cells'),
        actual_threads=telemetry.get('actual_threads'),max_cells_per_voxel=telemetry.get('max_cells_per_voxel'),
        due_updates=sum(int(r['due']) for r in updates) if updates else None,
        actual_updates=sum(int(r['actual']) for r in updates) if updates else None,
        min_concentration=telemetry.get('min_concentration'),
        final_biomass_pg=number(final.get('total_dry_mass_pg')),
        solver_failures=telemetry.get('solver_failures'),
        wall_seconds=metrics.get('resource',{}).get('elapsed_seconds'),
        peak_rss_kib=metrics.get('resource',{}).get('peak_rss_kib'),
        order_sha256=digest(order) if order.exists() else None,
        comparison_key=manifest['comparison_key'])
    fields=[]
    for r in rows(run/'inputs/benchmark_substrates.csv'):
        fields.append(dict(attempt=run.name,threads=case['threads'],order_seed=case['order_seed'],repeat=case['repeat'],**r))
    glucose=[number(r['min_concentration']) for r in fields if r['field_name']=='glucose']
    record['glucose_min_concentration']=min((v for v in glucose if v is not None),default=None)
    return record,fields


def paired_comparisons(records):
    """Require same seed/repeat, physics/binary identity and actual permutation."""
    result=[]
    for row in records:
        if row['threads']==1: continue
        serial=[r for r in records if r['threads']==1 and r['order_seed']==row['order_seed'] and r['repeat']==row['repeat'] and r.get('mesh_id')==row.get('mesh_id')]
        repeats=[r for r in records if r['case_id']==row['case_id']]
        pair={k:row[k] for k in ('attempt','case_id','threads','order_seed','repeat')}
        pair['mesh_id']=row.get('mesh_id','original')
        if len(serial)!=1 or len(repeats)!=1:
            pair['comparison']='missing_or_ambiguous_attempts'
        elif row['comparison_key']!=serial[0]['comparison_key'] or not row['order_sha256'] or row['order_sha256']!=serial[0]['order_sha256']:
            pair['comparison']='incompatible_workload_or_order'
        elif any(r['status'] not in ('completed','completed_flagged') or r['actual_threads']!=r['threads'] for r in (row,serial[0])):
            pair['comparison']='incomplete_or_invalid_thread_count'
        else:
            baseline=serial[0]; pair['comparison']='paired_including_diagnostic_flags'
            pair['serial_attempt']=baseline['attempt']
            pair['serial_flags']=baseline['flags']; pair['parallel_flags']=row['flags']
            for key in ('actual_updates','final_biomass_pg','min_concentration','glucose_min_concentration'):
                a,b=number(row.get(key)),number(baseline.get(key))
                pair[key+'_parallel_minus_serial']=a-b if a is not None and b is not None else None
        result.append(pair)
    return result


def serial_update_deficits(records):
    """Signed serial-minus-actual counts, using the validated matched comparisons."""
    deficits={r['attempt']:0 for r in records
              if r['threads']==1 and r['actual_threads']==1
              and r['status'] in ('completed','completed_flagged')
              and number(r['actual_updates']) is not None
              and sum(other['case_id']==r['case_id'] for other in records)==1}
    for pair in paired_comparisons(records):
        delta=pair.get('actual_updates_parallel_minus_serial')
        if pair['comparison']=='paired_including_diagnostic_flags' and delta is not None:
            deficits[pair['attempt']]=-delta
    return deficits


def plots(out,records,fields):
    meshes=sorted({r.get('mesh_id','original') for r in records})
    if len(meshes)>1:
        for mesh in meshes:
            dest=out/mesh; dest.mkdir()
            subset=[r for r in records if r.get('mesh_id')==mesh]
            attempts={r['attempt'] for r in subset}
            plots(dest,subset,[r for r in fields if r['attempt'] in attempts])
        mesh_overview(out,records)
        return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    deficits=serial_update_deficits(records)
    for index,seed in enumerate(sorted({r['order_seed'] for r in records})):
        data=[r for r in records if r['order_seed']==seed]
        for r in data:
            x=r['threads']+(r['repeat']-2)*0.08
            if number(r['glucose_min_concentration']) is not None: axes[0].scatter(x,r['glucose_min_concentration'],color=f'C{index}',label=str(seed) if r is data[0] else None)
            if r['attempt'] in deficits:
                axes[1].scatter(x,deficits[r['attempt']],color=f'C{index}')
    axes[0].axhline(0,color='black',linewidth=.5)
    axes[0].set(ylabel='Minimum glucose (mM)',xlabel='Requested threads')
    axes[0].legend(title='Order seed',fontsize=7)
    axes[1].set(ylabel='Missing intracellular updates\nrelative to serial',xlabel='Requested threads')
    axes[1].axhline(0,color='black',linewidth=.5)
    serial_counts={r['actual_updates'] for r in records if r['threads']==1 and r['attempt'] in deficits}
    if len(serial_counts)==1:
        axes[1].set_title(f'Serial reference: {next(iter(serial_counts)):g} updates')
    for ax in axes: ax.set_xticks([1,2,4,8])
    fig.suptitle('All recorded attempts; flagged outcomes retained')
    fig.tight_layout(); fig.savefig(out/'diagnostics.pdf'); fig.savefig(out/'diagnostics.png',dpi=180); plt.close(fig)
    seeds=sorted({r['order_seed'] for r in records})
    if seeds:
        fig,axes=plt.subplots(len(seeds),1,figsize=(8,2.3*len(seeds)),squeeze=False)
        colors={1:'black',2:'tab:blue',4:'tab:orange',8:'tab:green'}
        for ax,seed in zip(axes[:,0],seeds):
            for record in records:
                if record['order_seed']!=seed: continue
                data=[r for r in fields if r['attempt']==record['attempt'] and r['field_name']=='glucose' and r['phase']=='after_cell_step']
                ax.plot([float(r['time_minutes']) for r in data],[float(r['min_concentration']) for r in data],color=colors[record['threads']],alpha=.65,label=str(record['threads']) if record['repeat']==1 else None)
            ax.set(title=f'Order seed {seed}',ylabel='Minimum glucose (mM)'); ax.axhline(0,color='grey',linewidth=.5); ax.legend(title='Threads')
        axes[-1,0].set_xlabel('Simulation time (min)')
        fig.tight_layout(); fig.savefig(out/'glucose_by_seed.pdf'); fig.savefig(out/'glucose_by_seed.png',dpi=180); plt.close(fig)


def mesh_overview(out,records):
    """Show within-mesh serial differences against measured voxel occupancy."""
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    by_attempt={r['attempt']:r for r in records}
    colors={2:'tab:blue',4:'tab:orange',8:'tab:green'}
    labelled=set()
    for pair in paired_comparisons(records):
        if pair['comparison']!='paired_including_diagnostic_flags': continue
        r=by_attempt[pair['attempt']]
        occupancy=number(r['max_cells_per_voxel'])
        if occupancy is None: continue
        p=r['threads']; x=occupancy+{2:-.12,4:0,8:.12}[p]+(r['repeat']-2)*.025
        for ax,key,sign in ((axes[0],'actual_updates_parallel_minus_serial',-1),
                            (axes[1],'glucose_min_concentration_parallel_minus_serial',1)):
            delta=pair.get(key)
            if delta is not None:
                ax.scatter(x,sign*delta,color=colors[p],alpha=.65,s=22,
                           label=str(p) if (id(ax),p) not in labelled else None)
                labelled.add((id(ax),p))
    for ax in axes:
        ax.axhline(0,color='black',linewidth=.6)
        ax.set_xticks([1,2,4,8]); ax.set_xlabel('Observed maximum cells per voxel')
        ax.legend(title='Threads')
    axes[0].set_ylabel('Missing intracellular updates\nrelative to matched serial run')
    axes[1].set_ylabel('Minimum glucose difference (mM)\nparallel − matched serial')
    fig.suptitle('Fixed cell positions; serial reference on each mesh')
    fig.tight_layout(); fig.savefig(out/'mesh_comparison.png',dpi=180); fig.savefig(out/'mesh_comparison.pdf'); plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New report directory; contains tables/, plots/, data/')
    parser.add_argument('--plots',action='store_true')
    args=parser.parse_args()
    expected=[json.loads(line) for line in (args.campaign/'voxel_sharing/cases.jsonl').read_text().splitlines()]
    roots=sorted({p.parent for p in (args.campaign/'voxel_sharing/runs').rglob('manifest.json')})
    records=[]; fields=[]
    for run in roots:
        record,measurements=inspect_run(run); records.append(record); fields.extend(measurements)
    if not records: parser.error('No recorded attempts; no report created')
    args.output.mkdir(parents=True,exist_ok=False)
    for name in ('tables','plots','data'): (args.output/name).mkdir()
    coverage=[]
    for case in expected:
        attempts=[r for r in records if r['case_id']==case['case_id']]
        coverage.append(dict(case_id=case['case_id'],mesh_id=case.get('mesh_id','original'),threads=case['threads'],order_seed=case['order_seed'],repeat=case['repeat'],attempts=len(attempts),statuses=';'.join(r['status'] for r in attempts)))
    write_table(args.output/'tables/runs.csv',records)
    write_table(args.output/'tables/coverage.csv',coverage)
    write_table(args.output/'tables/paired_serial_parallel.csv',paired_comparisons(records))
    write_table(args.output/'tables/substrate_trajectories.csv',fields)
    # Small, sufficient raw evidence for readers; bulky snapshots/binaries stay local.
    evidence_hashes={}
    for run in roots:
        dest=args.output/'data'/run.name; dest.mkdir()
        files=[run/n for n in ('manifest.json','metrics.json','hardware.json','stdout.log','stderr.log','resource.tsv') if (run/n).is_file()]
        files+=list((run/'inputs').glob('benchmark_*.csv'))+list((run/'inputs').glob('benchmark_metrics.json'))
        if (run/'inputs/settings.xml').exists(): files.append(run/'inputs/settings.xml')
        for path in files:
            shutil.copy2(path,dest/path.name); evidence_hashes[f'data/{run.name}/{path.name}']=digest(path)
    for name in ('campaign.json','protocol.json','build.json'):
        shutil.copy2(args.campaign/name,args.output/name)
    write_json(args.output/'analysis.json',dict(script_sha256=digest(__file__),cases_expected=len(expected),attempts_observed=len(records),
        missing_cases=[r['case_id'] for r in coverage if r['attempts']==0],ambiguous_cases=[r['case_id'] for r in coverage if r['attempts']>1],
        note='Flags retained; a serial negative concentration alone is not evidence of a parallel race.',evidence_sha256=evidence_hashes))
    if args.plots: plots(args.output/'plots',records,fields)

if __name__=='__main__': main()
