#!/usr/bin/env python3
"""Validate and summarize an exported mesh report; no simulations or submissions."""
import argparse
from collections import Counter, defaultdict
import csv
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'performance'))
from common import digest, read_json, write_json
from analyze_growth import exchange_ledger_pass


def rows(path):
    with path.open() as stream: return list(csv.DictReader(stream))


def write_table(path, records):
    with path.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]),lineterminator='\n')
        writer.writeheader(); writer.writerows(records)


def summarize(report, output=None):
    if output is None:
        output=report
    else:
        output.mkdir(parents=True,exist_ok=False)
        (output/'tables').mkdir()
    audit=read_json(report/'analysis.json')
    for relative,expected in audit['evidence_sha256'].items():
        if digest(report/relative)!=expected: raise ValueError(f'Evidence checksum mismatch: {relative}')
    coverage=rows(report/'tables/coverage.csv')
    if any(int(r['attempts'])!=1 for r in coverage): raise ValueError('Missing or repeated attempts')
    records=rows(report/'tables/runs.csv'); pairs=rows(report/'tables/paired_serial_parallel.csv')
    if any(p['comparison']!='paired_including_diagnostic_flags' for p in pairs):
        raise ValueError('Serial comparison failed validation')
    if len(records)!=len(coverage) or len(pairs)!=sum(int(r['threads'])>1 for r in records):
        raise ValueError('Unexpected coverage or pair count')
    paired={p['attempt']:p for p in pairs}
    details=[]; orders=defaultdict(set); geometries=set(); epochs=set()
    for r in records:
        data=report/'data'/r['attempt']; case=read_json(data/'manifest.json')['case']
        metrics=read_json(data/'metrics.json')
        if metrics['returncode']!=0 or not metrics['final_snapshot_present']:
            raise ValueError('Incomplete simulation')
        if int(r['threads'])!=int(float(r['actual_threads'])): raise ValueError('Thread count mismatch')
        if (int(float(r['initial_cells'])),int(float(r['final_cells'])))!=(8,8): raise ValueError('Population changed')
        if int(float(r['max_cells_per_voxel']))!=int(r['expected_max_occupancy']): raise ValueError('Occupancy mismatch')
        positions=rows(data/'benchmark_positions.csv')
        by_id={int(p['cell_id']):tuple(float(p[a+'_um']) for a in 'xyz') for p in positions}
        expected={i:tuple(p) for i,p in enumerate(case['initial_positions'])}
        if by_id!=expected: raise ValueError('Unexpected initial positions')
        geometries.add(tuple(sorted(by_id.items())))
        occupied=Counter(int(p['voxel_index']) for p in positions)
        if max(occupied.values())!=int(r['expected_max_occupancy']): raise ValueError('Incorrect observed initial occupancy')
        orders[int(r['order_seed'])].add(r['order_sha256'])
        config=ET.parse(data/'settings.xml').getroot()
        epochs.add((float(config.findtext('overall/dt_diffusion')),
                    float(config.findtext('.//intracellular/settings/intracellular_dt'))))
        glucose=next(v for v in config.findall('microenvironment_setup/variable') if v.get('name')=='glucose')
        ledger=[row for row in rows(data/'benchmark_exchange_balance.csv') if int(row['field_index'])==int(glucose.get('ID'))]
        cells=rows(data/'benchmark_cells.csv')
        population=rows(data/'benchmark_population.csv')
        initial=next(p for p in population if p['phase']=='initial')
        final=next(p for p in reversed(population) if p['phase']=='final')
        substrates=[p for p in rows(data/'benchmark_substrates.csv') if p['field_name']=='glucose']
        g0=next(p for p in substrates if p['phase']=='initial')
        gf=next(p for p in reversed(substrates) if p['phase']=='final')
        missing=0 if int(r['threads'])==1 else -float(paired[r['attempt']]['actual_updates_parallel_minus_serial'])
        delta_glucose=0 if int(r['threads'])==1 else float(paired[r['attempt']]['glucose_min_concentration_parallel_minus_serial'])
        delta_mass=0 if int(r['threads'])==1 else float(paired[r['attempt']]['final_biomass_pg_parallel_minus_serial'])
        final_mass=float(final['total_dry_mass_pg']); reference_mass=final_mass-delta_mass
        details.append(dict(attempt=r['attempt'],mesh_id=r['mesh_id'],voxel_um=float(r['voxel_size_um']),
            occupancy=int(r['expected_max_occupancy']),threads=int(r['threads']),seed=int(r['order_seed']),repeat=int(r['repeat']),
            status=r['status'],flags=r['flags'],actual_updates=int(r['actual_updates']),due_updates=int(r['due_updates']),
            due_minus_actual=int(r['due_updates'])-int(r['actual_updates']),missing_vs_serial=missing,
            glucose_min_mM=float(r['glucose_min_concentration']),glucose_min_delta_vs_serial_mM=delta_glucose,
            glucose_final_total_mM_um3=float(gf['amount_concentration_um3']),glucose_initial_total_mM_um3=float(g0['amount_concentration_um3']),
            biomass_pg=final_mass,biomass_change_percent=100*(final_mass/float(initial['total_dry_mass_pg'])-1),
            biomass_delta_vs_serial_percent=100*delta_mass/reference_mass,
            nonoptimal_cell_updates=sum(c['primary_status']!='optimal' for c in cells),solver_failures=float(r['solver_failures']),
            glucose_exchange_ledger_pass=exchange_ledger_pass(ledger),
            glucose_exchange_max_abs_residual=max(abs(float(x['residual'])) for x in ledger),
            final_time_min=float(final['time_minutes'])))
    if len(geometries)!=1 or epochs!={(.01,.01)}: raise ValueError('Geometry or timestep controls changed')
    if any(len(v)!=1 for v in orders.values()) or len(set.union(*orders.values()))!=len(orders):
        raise ValueError('Seeds do not select distinct, consistent initialization orders')
    groups=defaultdict(list)
    for r in details: groups[(r['voxel_um'],r['threads'])].append(r)
    summary=[]
    for (spacing,threads),group in sorted(groups.items(),reverse=True):
        summary.append(dict(mesh_id=group[0]['mesh_id'],voxel_um=spacing,occupancy=group[0]['occupancy'],threads=threads,runs=len(group),
            flagged_runs=sum(bool(r['flags']) for r in group),negative_glucose_runs=sum(r['glucose_min_mM']<0 for r in group),
            missed_update_runs=sum(r['missing_vs_serial']>0 for r in group),
            missing_updates_min=min(r['missing_vs_serial'] for r in group),
            missing_updates_median=statistics.median(r['missing_vs_serial'] for r in group),
            missing_updates_max=max(r['missing_vs_serial'] for r in group),
            glucose_min_mM=min(r['glucose_min_mM'] for r in group),
            glucose_delta_vs_serial_min_mM=min(r['glucose_min_delta_vs_serial_mM'] for r in group),
            glucose_delta_vs_serial_max_mM=max(r['glucose_min_delta_vs_serial_mM'] for r in group),
            biomass_delta_vs_serial_min_percent=min(r['biomass_delta_vs_serial_percent'] for r in group),
            biomass_delta_vs_serial_max_percent=max(r['biomass_delta_vs_serial_percent'] for r in group),
            exchange_mismatch_runs=sum(not r['glucose_exchange_ledger_pass'] for r in group),
            max_exchange_abs_residual=max(r['glucose_exchange_max_abs_residual'] for r in group),
            nonoptimal_cell_updates=sum(r['nonoptimal_cell_updates'] for r in group)))
    repeats=[]
    for spacing,threads in sorted(groups):
        for seed in sorted(orders):
            group=[r for r in groups[spacing,threads] if r['seed']==seed]
            repeats.append(dict(voxel_um=spacing,threads=threads,seed=seed,runs=len(group),
                updates_range=max(r['actual_updates'] for r in group)-min(r['actual_updates'] for r in group),
                glucose_min_range_mM=max(r['glucose_min_mM'] for r in group)-min(r['glucose_min_mM'] for r in group),
                biomass_range_pg=max(r['biomass_pg'] for r in group)-min(r['biomass_pg'] for r in group)))
    write_table(output/'tables/mesh_run_diagnostics.csv',details)
    write_table(output/'tables/mesh_thread_summary.csv',summary)
    write_table(output/'tables/same_seed_repeats.csv',repeats)
    write_json(output/'mesh_validation.json',dict(script_sha256=digest(__file__),ledger_check_script_sha256=digest(HERE.parent/'performance/analyze_growth.py'),
        expected_cases=len(coverage),observed_attempts=len(records),matched_pairs=len(pairs),
        source_evidence_files_verified=len(audit['evidence_sha256']),statuses=dict(Counter(r['status'] for r in records)),
        serial_update_counts=sorted({r['actual_updates'] for r in details if r['threads']==1}),
        unique_geometries=len(geometries),orders_per_seed={k:sorted(v) for k,v in orders.items()},
        final_times=sorted({r['final_time_min'] for r in details}),
        note='Descriptive ranges across 5 initialization orders and 3 same-seed repeats; no causal attribution or independence assumption. Ledger precision tolerance is inherited from the growth analysis.'))
    print('Validated',len(records),'runs and',len(pairs),'matched serial/parallel comparisons.')
    for r in summary: print(r)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--report',type=Path,required=True)
    p.add_argument('--output',type=Path,help='New directory for regenerated summaries; leaves the archived report unchanged')
    args=p.parse_args()
    summarize(args.report,args.output)


if __name__=='__main__': main()
