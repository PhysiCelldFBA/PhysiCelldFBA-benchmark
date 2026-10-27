#!/usr/bin/env python3
"""Analyze serial medium controls in the activated analysis environment."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from common import digest, read_json, write_json


def rows(path):
    if not path.exists() and path.with_suffix(path.suffix+'.gz').exists():
        path=path.with_suffix(path.suffix+'.gz')
    if not path.exists(): return []
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt') as stream: return list(csv.DictReader(stream))


def table(path, data):
    if not data: raise ValueError(f'No rows for {path}')
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)


def exchange_ledger_pass(ledger):
    """Floating-point accounting check, not a biological accuracy tolerance."""
    checked=0
    for row in ledger:
        if row['net_export_only']!='1':
            return False  # This control requires the recorded net-export ledger.
        checked+=1
        scale=max(1.,abs(float(row['before_amount'])),abs(float(row['after_amount'])))
        exchange=max(abs(float(row['observed_delta'])),abs(float(row['expected_net_export_delta'])))
        if abs(float(row['residual']))>1e-10*scale+1e-8*exchange:
            return False
    return checked>0


def local_endpoints(run):
    """Use installed pctk for matrices; read fractional snapshot time from XML."""
    cached=run/'local_endpoints.csv'
    if cached.exists(): return rows(cached)
    from pctk.multicellds import MultiCellDS
    import numpy as np
    from scipy.spatial import cKDTree
    positions=rows(run/'inputs/benchmark_positions.csv')
    result=[]
    for phase in ('initial','final'):
        output=run/'inputs/output'; xml=output/(phase+'.xml')
        if not xml.exists(): continue
        tree=ET.parse(xml); snapshot=MultiCellDS(str(output),phase+'.xml')
        matrix=snapshot.get_microenvironment_matrix(tree)
        if matrix is None: raise ValueError(f'Cannot load {xml}')
        xyz=np.array([[float(p[a+'_um']) for a in 'xyz'] for p in positions])
        distances,indices=cKDTree(matrix[:3].T).query(xyz)
        for p,index in zip(positions,indices):
            if int(p['voxel_index'])!=int(index): raise ValueError('Snapshot voxel order does not match initial positions')
            for field,units,field_id in snapshot.microenvironment_columns:
                result.append(dict(phase=phase,time_minutes=float(tree.findtext('metadata/current_time')),
                    cell_id=int(p['cell_id']),field=field,concentration_mM=float(matrix[4+int(field_id),index])))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    runs=sorted(p.parent for p in args.runs.rglob('metrics.json') if (p.parent/'manifest.json').exists())
    if not runs: raise ValueError('No runs found')
    if any(read_json(p/'metrics.json')['status']=='incomplete_or_terminated' for p in runs):
        raise ValueError('Wait for all runs to finish before final analysis')
    args.output.mkdir(parents=True,exist_ok=False)
    for folder in ('tables','plots','data'): (args.output/folder).mkdir()
    summaries=[]; curves=[]; endpoints=[]; evidence={}
    for run in runs:
        manifest=read_json(run/'manifest.json'); case=manifest['case']; metrics=read_json(run/'metrics.json')
        ident=case['case_id']; data=args.output/'data'/ident; data.mkdir(); (data/'inputs').mkdir()
        for name in ('manifest.json','metrics.json','hardware.json','resource.tsv','command.json'):
            if (run/name).exists(): shutil.copy2(run/name,data/name)
        for name in ('settings.xml','input-record.json'):
            shutil.copy2(run/'inputs'/name,data/'inputs'/name)
        evidence[ident]={}
        for name in ('benchmark_cells.csv','benchmark_population.csv','benchmark_substrates.csv',
                     'benchmark_update_counts.csv','benchmark_positions.csv','benchmark_exchange_balance.csv','benchmark_fluxes.csv'):
            source=run/'inputs'/name
            if source.exists():
                evidence[ident][name]=digest(source)
                with source.open('rb') as src, gzip.open(data/'inputs'/(name+'.gz'),'wb') as dest: shutil.copyfileobj(src,dest)
            elif source.with_suffix('.csv.gz').exists():
                shutil.copy2(source.with_suffix('.csv.gz'),data/'inputs'/(name+'.gz'))
        local=local_endpoints(run)
        for phase in ('initial','final'):
            xml=run/'inputs/output'/(phase+'.xml')
            if xml.exists():
                matrix=xml.parent/ET.parse(xml).findtext('microenvironment/domain/data/filename')
                evidence[ident][f'{phase}_snapshot_xml']=digest(xml)
                evidence[ident][f'{phase}_microenvironment_mat']=digest(matrix)
        if local: table(data/'local_endpoints.csv',local)
        endpoints.extend(dict(case_id=ident,**r) for r in local)
        cells=rows(run/'inputs/benchmark_cells.csv'); pop=rows(run/'inputs/benchmark_population.csv')
        updates=rows(run/'inputs/benchmark_update_counts.csv'); substrates=rows(run/'inputs/benchmark_substrates.csv')
        ledger=rows(run/'inputs/benchmark_exchange_balance.csv')
        first=next(r for r in pop if r['phase']=='initial'); last=next(r for r in reversed(pop) if r['phase']=='final')
        mass0=float(first['total_dry_mass_pg']); mass1=float(last['total_dry_mass_pg'])
        growth=[float(c['growth_per_hour']) for c in cells]
        bad=sum(c['primary_status']!='optimal' for c in cells)
        telemetry=metrics['telemetry']; flags=telemetry.get('diagnostic_flags',[])
        mismatch=sum(abs(int(r['due'])-int(r['actual'])) for r in updates)
        field_minima={}
        for row in substrates:
            name=row['field_name']; value=float(row['min_concentration'])
            field_minima[name]=min(value,field_minima.get(name,value))
        passed=bool(cells) and metrics['status']=='completed' and not bad and not mismatch and min(growth)>0
        passed=passed and (case['fixed_volume'] or mass1>mass0)
        ledger_pass=exchange_ledger_pass(ledger)
        passed=passed and ledger_pass
        concentrations={}
        for phase in ('initial','final'):
            for label,names in (('oxygen',('oxygen','O2')),('glucose',('glucose','D-Glucose'))):
                vals=[float(r['concentration_mM']) for r in local if r['phase']==phase and r['field'] in names]
                concentrations[f'{phase}_local_{label}_min_mM']=min(vals) if vals else None
                concentrations[f'{phase}_local_{label}_max_mM']=max(vals) if vals else None
        summaries.append(dict(case_id=ident,medium_profile=case['medium_profile'],model=case['model'],variant=case['variant'],
            cells=case['cells_requested'],fixed_volume=case['fixed_volume'],dt_minutes=case['intracellular_dt_minutes'],
            final_time_minutes=float(last['time_minutes']),status=metrics['status'],flags=';'.join(flags),
            primary_nonoptimal_updates=bad,solver_failures=telemetry.get('solver_failures',0),
            stage_two_failures=telemetry.get('stage_two_failures',0),update_mismatch=mismatch,
            intracellular_updates=len(cells),max_cells_per_voxel=telemetry['max_cells_per_voxel'],
            growth_min_per_hour=min(growth) if growth else None,growth_mean_per_hour=sum(growth)/len(growth) if growth else None,
            biomass_change_percent=100*(mass1/mass0-1),min_field_concentration_mM=telemetry['min_concentration'],
            negative_fields=';'.join(f'{k}:{v:.9g}' for k,v in field_minima.items() if v<0),
            exchange_max_abs_residual=max((abs(float(r['residual'])) for r in ledger),default=0),
            exchange_max_relative_residual=max((abs(float(r['residual']))/max(1.,abs(float(r['before_amount'])),abs(float(r['after_amount']))) for r in ledger),default=0),
            exchange_ledger_pass=ledger_pass,
            short_control_pass=passed,wall_seconds=metrics['resource'].get('elapsed_seconds'),
            peak_rss_kib=metrics['resource'].get('peak_rss_kib'),**concentrations))
        for row in pop:
            if row['phase'] in ('initial','after_cell_step','final'):
                curves.append(dict(case_id=ident,time_minutes=float(row['time_minutes']),
                    biomass_change_percent=100*(float(row['total_dry_mass_pg'])/mass0-1)))
    table(args.output/'tables/summary.csv',summaries); table(args.output/'tables/biomass.csv',curves)
    if endpoints: table(args.output/'tables/local_endpoints.csv',endpoints)
    write_json(args.output/'analysis.json',dict(script_sha256=digest(__file__),runs=len(runs),evidence=evidence,
        statuses=dict(Counter(r['status'] for r in summaries)),
        criterion='Completed without diagnostic flags, all recorded primary solves optimal, positive growth at every update, matched due/actual updates, exchange ledger consistent; biomass increases when growth is enabled. Necessary short-run check, not proof of numerical accuracy, long-run supply or scalability.',
        exchange_ledger_tolerance='abs(residual) <= 1e-10 * max(1, abs(before), abs(after)) + 1e-8 * max(abs(observed_delta), abs(expected_net_export_delta)); all rows must be net_export_only. Floating-point accounting tolerance, not the study accuracy criterion.',
        limitations=['Endpoint local concentrations only; global field minima and per-cell growth monitored throughout.',
                    'Cell-exchange ledger excludes diffusion and external supply; not a whole-system mass balance.',
                    'Frozen-volume cases assess positive LP growth, not accumulated biomass.',
                    'Diagnostic I/O and serial allocations are unsuitable for published performance timing.']))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    profiles=sorted({r['medium_profile'] for r in summaries if r['cells']==1 and r['variant']=='dfba'})
    fig,axes=plt.subplots(2,3,figsize=(13,7),constrained_layout=True)
    for ax,name in zip(axes.flat,profiles):
        for row in summaries:
            if row['medium_profile']!=name or row['cells']!=1 or row['variant']!='dfba': continue
            points=[p for p in curves if p['case_id']==row['case_id']]
            label=f"dt = {row['dt_minutes']:g} min"+(' (fails checks)' if not row['short_control_pass'] else '')
            ax.plot([p['time_minutes'] for p in points],[p['biomass_change_percent'] for p in points],label=label)
        ax.set(title=name.replace('_',' '),xlabel='Time (min)',ylabel='Dry biomass increase (%)'); ax.legend(fontsize=8)
    for ext in ('png','pdf'): fig.savefig(args.output/'plots'/('single_cell_growth.'+ext),dpi=180)
    plt.close(fig)
    print(json.dumps(summaries,indent=2))


if __name__=='__main__': main()
