#!/usr/bin/env python3
"""Manual diagnostic analysis from benchmark telemetry (not snapshot parsing).

Use the documented analysis environment. pctk remains the preferred reader for
additional MultiCellDS snapshot variables. Failed/flagged runs remain included.
"""
import argparse
import csv
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from common import read_json, write_json


def rows(path):
    if not path.is_file(): return []
    with path.open() as f: return list(csv.DictReader(f))


def curve(run):
    data=rows(run/'inputs/benchmark_population.csv')
    return sorted([(float(r['time_minutes']),float(r['total_dry_mass_pg'])) for r in data if r['phase'] in ('initial','after_cell_step','final')])


def comparison_signature(run, timestep=False, variant=False):
    manifest=read_json(run/'manifest.json')
    root=ET.parse(run/'inputs/settings.xml').getroot()
    def normalized(node,path=''):
        path=path+'/'+node.tag
        if timestep and (path.endswith('/overall/dt_diffusion') or path.endswith('/settings/intracellular_dt') or path.endswith('/settings/time_step') or path.endswith('/full_data/interval')): return None
        if variant and node.tag=='secondary_objective': return None
        return (node.tag,sorted(node.attrib.items()),(node.text or '').strip(),[value for child in node if (value:=normalized(child,path)) is not None])
    assets={k:v for k,v in manifest['files'].items() if k=='simulation' or (k.startswith('inputs/') and k not in ('inputs/settings.xml','inputs/input-record.json'))}
    return normalized(root),assets


def finite_json(value):
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,dict): return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value,list): return [finite_json(v) for v in value]
    return value


def field_curves(run):
    result={}
    for r in rows(run/'inputs/benchmark_substrates.csv'):
        if r['phase'] not in ('initial','after_cell_step','final'): continue
        result.setdefault(r['field_name'],[]).append((float(r['time_minutes']),float(r['amount_concentration_um3'])))
    return result


def interpolate(data,t):
    # Collapse repeated timestamps to the last phase at that timestamp.
    points=sorted(dict(data).items())
    if not points or t<points[0][0] or t>points[-1][0]: return None
    import bisect
    i=bisect.bisect_left([p[0] for p in points],t)
    if i==0 or points[i][0]==t: return points[i][1]
    a,b=points[i-1],points[i]
    return a[1]+(b[1]-a[1])*(t-a[0])/(b[0]-a[0])


def outcome(run, yield_gdw_per_g_glucose=None, glucose_name='glucose'):
    manifest=read_json(run/'manifest.json'); metrics=read_json(run/'metrics.json')
    case=manifest['case']; telemetry=metrics.get('telemetry') or {}
    population=rows(run/'inputs/benchmark_population.csv')
    initial=next((r for r in population if r['phase']=='initial'),None)
    final=next((r for r in reversed(population) if r['phase']=='final'),None)
    result=dict(run=str(run),case_id=case['case_id'],phase=case['phase'],model=case['model'],variant=case['variant'],
                status=metrics['status'],flags=telemetry.get('diagnostic_flags',[]),
                wall_seconds=metrics.get('resource',{}).get('elapsed_seconds'),
                initial_dry_mass_pg=float(initial['total_dry_mass_pg']) if initial else None,
                final_dry_mass_pg=float(final['total_dry_mass_pg']) if final else None,
                biomass_error_fraction=None,expected_new_biomass_pg=None,glucose_remaining_fraction=None,
                exchange_max_abs_residual=None)
    ledger=[r for r in rows(run/'inputs/benchmark_exchange_balance.csv') if r['net_export_only']=='1']
    if ledger: result['exchange_max_abs_residual']=max(abs(float(r['residual'])) for r in ledger)
    substrates=rows(run/'inputs/benchmark_substrates.csv')
    glucose=[r for r in substrates if r['field_name']==glucose_name]
    g0=next((float(r['amount_concentration_um3']) for r in glucose if r['phase']=='initial'),None)
    gf=next((float(r['amount_concentration_um3']) for r in reversed(glucose) if r['phase']=='final'),None)
    if g0 is not None and gf is not None and g0>0:
        result['glucose_remaining_fraction']=gf/g0
        if yield_gdw_per_g_glucose is not None and case['model']=='ecoli_core' and case['phase']=='timestep' and initial and final:
            # mM*um3 -> mmol (/1e15) -> g glucose (*180/1000)
            # -> gDW (*yield) -> pg (*1e12). Initial biomass is excluded.
            produced=(g0-gf)*180.0/1e6*yield_gdw_per_g_glucose
            result['expected_new_biomass_pg']=produced
            if produced>0:
                result['biomass_error_fraction']=(result['final_dry_mass_pg']-result['initial_dry_mass_pg']-produced)/produced
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('roots',nargs='+',type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--verified-yield',type=float,help='Independently verified constant gDW/g glucose; never inferred from these runs')
    p.add_argument('--yield-record',type=Path,help='Required evidence for the supplied yield and its applicable conditions')
    p.add_argument('--reference-run',type=Path,help='Explicit numerical reference for matched cancer/workload curves')
    p.add_argument('--paired-run',type=Path,help='Explicit matched FBA/pFBA counterpart; only secondary objective may differ')
    p.add_argument('--plots',action='store_true')
    args=p.parse_args()
    if args.verified_yield is not None and (not math.isfinite(args.verified_yield) or args.verified_yield<=0 or not args.yield_record or not args.yield_record.is_file()):
        p.error('A positive verified yield requires an existing evidence record')
    runs=sorted({x.parent.resolve() for root in args.roots for x in root.rglob('metrics.json') if (x.parent/'manifest.json').is_file()})
    if not runs: p.error('No benchmark runs found')
    reports=[outcome(r,args.verified_yield) for r in runs]
    # No automatic reference selection: a low dt run is not necessarily accurate.
    if args.reference_run and args.paired_run: p.error('Choose either timestep reference or FBA/pFBA pairing')
    if args.reference_run or args.paired_run:
        ref=(args.reference_run or args.paired_run).resolve(); refmanifest=read_json(ref/'manifest.json'); refcurve=curve(ref)
        refcase=refmanifest['case']
        reference_signature=comparison_signature(ref,timestep=bool(args.reference_run),variant=bool(args.paired_run))
        for run,report in zip(runs,reports):
            case=read_json(run/'manifest.json')['case']
            if comparison_signature(run,timestep=bool(args.reference_run),variant=bool(args.paired_run)) != reference_signature:
                report['reference_comparison']='incompatible_case'; continue
            # Inputs/mesh differ by design in refinement; operator must review the
            # explicit reference. Compare shared physical times, no extrapolation.
            deltas=[]
            for t,b in curve(run):
                rb=interpolate(refcurve,t)
                if rb is not None: deltas.append(abs(b-rb))
            report['reference_comparison']='explicit_user_reference'
            report['biomass_max_abs_difference_pg']=max(deltas) if deltas else None
            if args.paired_run:
                resource=read_json(ref/'metrics.json').get('resource',{})
                wall=resource.get('elapsed_seconds')
                report['paired_wall_ratio']=report['wall_seconds']/wall if wall and report['wall_seconds'] is not None else None
                report['paired_run']=str(ref)
            reference_fields=field_curves(ref)
            field_errors={}
            for name,data in field_curves(run).items():
                errors=[]
                for t,value in data:
                    expected=interpolate(reference_fields.get(name,[]),t)
                    if expected is not None: errors.append(abs(value-expected))
                field_errors[name]=max(errors) if errors else None
            report['substrate_max_abs_differences']=field_errors
    reports=finite_json(reports)
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'outcomes.json',reports)
    write_json(args.output/'analysis_settings.json',dict(verified_yield=args.verified_yield,yield_record=str(args.yield_record) if args.yield_record else None,reference_run=str(args.reference_run) if args.reference_run else None,paired_run=str(args.paired_run) if args.paired_run else None))
    keys=sorted({k for r in reports for k in r})
    with (args.output/'outcomes.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(reports)
    if args.plots:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots()
        for run,report in zip(runs,reports):
            data=curve(run)
            if data: ax.plot(*zip(*data),label=report['case_id']+' ['+report['status']+']')
        ax.set(xlabel='Simulation time (min)',ylabel='Total dry biomass (pg)')
        ax.legend(fontsize=5,bbox_to_anchor=(1,1));fig.savefig(args.output/'biomass.pdf',bbox_inches='tight');plt.close(fig)
        fig,ax=plt.subplots()
        for r in reports:
            if r['biomass_error_fraction'] is not None and r['wall_seconds'] is not None:
                ax.scatter(r['wall_seconds'],abs(r['biomass_error_fraction']),label=r['case_id'])
        ax.set(xlabel='Wall time (s; compare identical output policies)',ylabel='Absolute biomass-yield error fraction')
        fig.savefig(args.output/'error_runtime.pdf',bbox_inches='tight');plt.close(fig)

if __name__=='__main__': main()
