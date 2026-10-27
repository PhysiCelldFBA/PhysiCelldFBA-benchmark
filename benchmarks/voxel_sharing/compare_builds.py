#!/usr/bin/env python3
"""Compare exported shared-voxel/mesh reports from two builds; no simulations or submissions.

Each parallel run is compared with the serial run of the same build, mesh, seed and
repetition; serial runs are also compared across builds. Reports come from analyze.py.
"""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'performance'))
from common import digest, read_json, write_json
from analyze_growth import exchange_ledger_pass

MESHES=('original','mesh16','mesh8','mesh4','mesh2')
MESH_LABELS={'original':'coincident\n8/voxel','mesh16':'16 µm\n8/voxel','mesh8':'8 µm\n4/voxel',
             'mesh4':'4 µm\n2/voxel','mesh2':'2 µm\n1/voxel'}


def rows(path):
    with path.open() as stream: return list(csv.DictReader(stream))


def write_table(path, records):
    with path.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]),lineterminator='\n')
        writer.writeheader(); writer.writerows(records)


def max_abs(a, b):
    """Largest elementwise difference; None when the series are not aligned."""
    if a.keys()!=b.keys(): return None
    return max((abs(a[k]-b[k]) for k in a),default=0.0)


def load_report(report, build_label):
    audit=read_json(report/'analysis.json')
    for relative,expected in audit['evidence_sha256'].items():
        if digest(report/relative)!=expected: raise ValueError(f'Evidence checksum mismatch: {report/relative}')
    commit=read_json(report/'build.json')['source_commit']
    pairs={p['attempt']:p for p in rows(report/'tables/paired_serial_parallel.csv')}
    trajectories=defaultdict(dict)
    for r in rows(report/'tables/substrate_trajectories.csv'):
        if r['field_name']=='glucose' and r['phase']=='after_cell_step':
            trajectories[r['attempt']][float(r['time_minutes'])]=float(r['min_concentration'])
    runs=[]
    for r in rows(report/'tables/runs.csv'):
        data=report/'data'/r['attempt']
        config=ET.parse(data/'settings.xml').getroot()
        glucose=next(v for v in config.findall('microenvironment_setup/variable') if v.get('name')=='glucose')
        ledger=[x for x in rows(data/'benchmark_exchange_balance.csv') if int(x['field_index'])==int(glucose.get('ID'))]
        mass={}
        for c in rows(data/'benchmark_cells.csv'): mass[int(c['cell_id'])]=float(c['dry_mass_pg'])
        runs.append(dict(build=build_label,source_commit=commit,report=str(report),attempt=r['attempt'],
            mesh_id=r.get('mesh_id','original'),threads=int(r['threads']),seed=int(r['order_seed']),repeat=int(r['repeat']),
            status=r['status'],actual_threads=int(float(r['actual_threads'])),actual_updates=int(r['actual_updates']),
            glucose_min_mM=float(r['glucose_min_concentration']),
            glucose_exchange_ledger_pass=exchange_ledger_pass(ledger),
            pair=pairs.get(r['attempt']),trajectory=trajectories[r['attempt']],final_mass=mass))
    return runs


def compare(a, b):
    """Glucose-trajectory and final per-cell dry-mass differences between two runs."""
    mass=max_abs(a['final_mass'],b['final_mass'])
    reference=max(a['final_mass'].values(),default=0.0)
    return dict(updates_difference=b['actual_updates']-a['actual_updates'],
        glucose_trajectory_max_abs_diff_mM=max_abs(a['trajectory'],b['trajectory']),
        cell_dry_mass_max_rel_diff=None if mass is None or not reference else mass/reference)


def paired(runs):
    serial={(r['build'],r['mesh_id'],r['seed'],r['repeat']):r for r in runs if r['threads']==1}
    out=[]
    for r in runs:
        base=serial.get((r['build'],r['mesh_id'],r['seed'],r['repeat']))
        row={k:r[k] for k in ('build','source_commit','mesh_id','threads','seed','repeat','attempt','status',
                              'actual_threads','actual_updates','glucose_min_mM','glucose_exchange_ledger_pass')}
        if r['threads']==1:
            row.update(serial_attempt=r['attempt'],validated_pair=True,missing_updates_vs_serial=0,
                       glucose_trajectory_max_abs_diff_mM=0.0,cell_dry_mass_max_rel_diff=0.0)
        else:
            valid=(base is not None and r['pair'] is not None
                   and r['pair']['comparison']=='paired_including_diagnostic_flags'
                   and r['pair']['serial_attempt']==base['attempt'])
            d=compare(base,r) if valid else {}
            row.update(serial_attempt=base['attempt'] if base else None,validated_pair=valid,
                       missing_updates_vs_serial=-d['updates_difference'] if valid else None,
                       glucose_trajectory_max_abs_diff_mM=d.get('glucose_trajectory_max_abs_diff_mM'),
                       cell_dry_mass_max_rel_diff=d.get('cell_dry_mass_max_rel_diff'))
        out.append(row)
    return out


def summarize(records):
    groups=defaultdict(list)
    for r in records: groups[(r['build'],r['mesh_id'],r['threads'])].append(r)
    order={m:i for i,m in enumerate(MESHES)}
    out=[]
    for (build,mesh,threads),g in sorted(groups.items(),key=lambda x:(x[0][0],order.get(x[0][1],99),x[0][2])):
        valid=[r for r in g if r['validated_pair']]
        traj=[r['glucose_trajectory_max_abs_diff_mM'] for r in valid if r['glucose_trajectory_max_abs_diff_mM'] is not None]
        mass=[r['cell_dry_mass_max_rel_diff'] for r in valid if r['cell_dry_mass_max_rel_diff'] is not None]
        out.append(dict(build=build,mesh_id=mesh,threads=threads,runs=len(g),validated_pairs=len(valid),
            thread_count_mismatches=sum(r['actual_threads']!=r['threads'] for r in g),
            missed_update_runs=sum(r['missing_updates_vs_serial']>0 for r in valid),
            missing_updates_max=max((r['missing_updates_vs_serial'] for r in valid),default=None),
            exchange_mismatch_runs=sum(not r['glucose_exchange_ledger_pass'] for r in g),
            negative_glucose_runs=sum(r['glucose_min_mM']<0 for r in g),
            glucose_min_mM=min(r['glucose_min_mM'] for r in g),
            identical_to_serial_runs=sum(r['missing_updates_vs_serial']==0 and r['glucose_trajectory_max_abs_diff_mM']==0
                                         and r['cell_dry_mass_max_rel_diff']==0 for r in valid),
            glucose_trajectory_max_abs_diff_mM=max(traj,default=None),
            cell_dry_mass_max_rel_diff=max(mass,default=None)))
    return out


def serial_across_builds(runs, before, after):
    serial={(r['build'],r['mesh_id'],r['seed'],r['repeat']):r for r in runs if r['threads']==1}
    out=[]
    for (build,mesh,seed,repeat),a in sorted(serial.items()):
        if build!=before: continue
        b=serial.get((after,mesh,seed,repeat))
        if b is None: continue
        out.append(dict(mesh_id=mesh,seed=seed,repeat=repeat,before_attempt=a['attempt'],after_attempt=b['attempt'],
            before_updates=a['actual_updates'],after_updates=b['actual_updates'],
            before_glucose_min_mM=a['glucose_min_mM'],after_glucose_min_mM=b['glucose_min_mM'],**compare(a,b)))
    return out


def plot(out, records, builds):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={2:'#2a78d6',4:'#eb6834',8:'#1baf7a'}
    markers={2:'o',4:'s',8:'^'}
    meshes=[m for m in MESHES if any(r['mesh_id']==m for r in records)]
    fig,axes=plt.subplots(2,len(builds),figsize=(5.2*len(builds),7.2),sharey='row',squeeze=False)
    for col,build in enumerate(builds):
        for r in records:
            if r['build']!=build or r['threads']==1 or not r['validated_pair']: continue
            x=meshes.index(r['mesh_id'])+{2:-.2,4:0,8:.2}[r['threads']]+(r['repeat']-2)*.04
            for row,key in enumerate(('missing_updates_vs_serial','glucose_trajectory_max_abs_diff_mM')):
                if r[key] is None: continue
                axes[row,col].scatter(x,r[key],s=26,color=colors[r['threads']],marker=markers[r['threads']],
                                      alpha=.7,linewidths=0,label=str(r['threads']))
        commits=sorted({r['source_commit'][:8] for r in records if r['build']==build})
        axes[0,col].set_title(f'{build} ({", ".join(commits)})')
        for row in range(2):
            ax=axes[row,col]
            ax.axhline(0,color='#888888',linewidth=.6)
            ax.set_xticks(range(len(meshes))); ax.set_xticklabels([MESH_LABELS[m] for m in meshes],fontsize=8)
            ax.grid(axis='y',color='#e5e5e5',linewidth=.5); ax.set_axisbelow(True)
            for side in ('top','right'): ax.spines[side].set_visible(False)
        axes[1,col].set_yscale('symlog',linthresh=1e-12)
    axes[0,0].set_ylabel('Missing intracellular updates\nrelative to matched serial run')
    axes[1,0].set_ylabel('Max |glucose min. difference| (mM)\nover trajectory vs matched serial')
    handles,labels=axes[0,0].get_legend_handles_labels()
    unique=dict(zip(labels,handles))
    fig.legend([unique[k] for k in sorted(unique,key=int)],sorted(unique,key=int),title='Threads',loc='upper right',frameon=False)
    fig.suptitle('Parallel runs against the serial run of the same build, mesh, seed and repetition',fontsize=10)
    fig.tight_layout(rect=(0,0,.93,1))
    fig.savefig(out/'before_after.png',dpi=180); fig.savefig(out/'before_after.pdf'); plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',type=Path,nargs='+',required=True,help='Reports from the earlier build')
    p.add_argument('--after',type=Path,nargs='+',required=True,help='Reports from the later build')
    p.add_argument('--labels',nargs=2,default=('before','after'))
    p.add_argument('--output',type=Path,required=True,help='New directory')
    p.add_argument('--plots',action='store_true')
    args=p.parse_args()
    before,after=args.labels
    runs=[r for rep in args.before for r in load_report(rep,before)]+[r for rep in args.after for r in load_report(rep,after)]
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'tables').mkdir()
    records=paired(runs); summary=summarize(records); serial=serial_across_builds(runs,before,after)
    write_table(args.output/'tables/attempts.csv',records)
    write_table(args.output/'tables/summary.csv',summary)
    if serial: write_table(args.output/'tables/serial_across_builds.csv',serial)
    write_json(args.output/'comparison.json',dict(script_sha256=digest(__file__),
        ledger_check_script_sha256=digest(HERE.parent/'performance/analyze_growth.py'),
        builds={label:sorted({r['source_commit'] for r in runs if r['build']==label}) for label in (before,after)},
        reports={label:[str(x) for x in reps] for label,reps in ((before,args.before),(after,args.after))},
        report_analysis_sha256={str(rep):digest(rep/'analysis.json') for rep in args.before+args.after},
        attempts=len(records),unvalidated_pairs=sum(not r['validated_pair'] for r in records),
        serial_pairs_across_builds=len(serial),
        serial_identical_across_builds=sum(s['updates_difference']==0 and s['glucose_trajectory_max_abs_diff_mM']==0
                                           and s['cell_dry_mass_max_rel_diff']==0 for s in serial),
        note='Glucose differences use after_cell_step voxel minima; dry-mass differences use each cell\'s last recorded update. No tolerance is applied; zero means bitwise equal recorded values.'))
    if args.plots:
        (args.output/'plots').mkdir(); plot(args.output/'plots',records,(before,after))
    for s in summary: print(s)
    print('Serial runs identical across builds:',sum(s['updates_difference']==0 and s['glucose_trajectory_max_abs_diff_mM']==0 and s['cell_dry_mass_max_rel_diff']==0 for s in serial),'of',len(serial))


if __name__=='__main__': main()
