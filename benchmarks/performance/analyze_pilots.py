#!/usr/bin/env python3
"""Export serial timestep pilot evidence and figures; never run simulations."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from common import digest,read_json,write_json
from analyze_outcomes import rows,outcome,comparison_signature


def table(path,records):
    with path.open('x',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=sorted({k for r in records for k in r}))
        w.writeheader(); w.writerows(records)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    expected=[json.loads(line) for line in (args.campaign/'timestep/cases.jsonl').read_text().splitlines()]
    runs=sorted(p.parent for p in (args.campaign/'timestep/runs').glob('*/manifest.json'))
    cases=[read_json(r/'manifest.json')['case'] for r in runs]
    if sorted(c['case_id'] for c in cases)!=sorted(c['case_id'] for c in expected):
        raise ValueError('Pilot coverage is incomplete, duplicated or unexpected')
    # Compare only matched scientific inputs, allowing timestep/output interval differences.
    for model in {c['model'] for c in cases}:
        group=[r for r,c in zip(runs,cases) if c['model']==model]
        signature=comparison_signature(group[0],timestep=True)
        if any(comparison_signature(r,timestep=True)!=signature for r in group):
            raise ValueError('Incompatible scientific inputs within model '+model)
    out=args.output; out.mkdir(parents=True,exist_ok=False)
    for folder in ('tables','plots','data'): (out/folder).mkdir()
    records=[]; trajectories=[]; per_update=[]; hashes={}; copied={}
    for run,c in zip(runs,cases):
        metrics=read_json(run/'metrics.json'); t=metrics['telemetry']
        root=ET.parse(run/'inputs/settings.xml').getroot()
        final=ET.parse(run/'inputs/output/final.xml').find('.//current_time')
        if metrics['returncode']!=0 or final is None: raise ValueError('Incomplete simulation '+str(run))
        glucose_name=next(v.get('name') for v in root.findall('microenvironment_setup/variable') if v.get('name').lower() in ('glucose','d-glucose'))
        rec=outcome(run,glucose_name=glucose_name)
        rec.update(diffusion_dt_minutes=c['diffusion_dt_minutes'],intracellular_dt_minutes=c['intracellular_dt_minutes'],
                   ratio=c['intracellular_dt_minutes']/c['diffusion_dt_minutes'],
                   final_time_minutes=float(final.text),actual_threads=t['actual_threads'],
                   actual_updates=t['intracellular_updates'],solver_failures=t.get('solver_failures',0),
                   peak_rss_kib=metrics['resource'].get('peak_rss_kib'))
        fields=[r for r in rows(run/'inputs/benchmark_substrates.csv') if r['field_name'].lower() in ('glucose','d-glucose')]
        if not fields: raise ValueError('No glucose field found')
        rec['minimum_glucose_mM']=min(float(r['min_concentration']) for r in fields)
        rec['biomass_change_percent']=100*(rec['final_dry_mass_pg']/rec['initial_dry_mass_pg']-1)
        glucose={r['time_minutes']:float(r['min_concentration']) for r in fields if r['phase']=='after_cell_step'}
        volume=t['voxel_count']
        for axis in 'xyz': volume*=float(root.findtext('domain/d'+axis))
        mean_glucose={r['time_minutes']:float(r['amount_concentration_um3'])/volume for r in fields if r['phase']=='after_cell_step'}
        for p in rows(run/'inputs/benchmark_population.csv'):
            if p['phase']!='after_cell_step': continue
            trajectories.append(dict(case_id=c['case_id'],model=c['model'],phase=c['phase'],ratio=rec['ratio'],
                diffusion_dt_minutes=c['diffusion_dt_minutes'],time_minutes=float(p['time_minutes']),
                dry_mass_pg=float(p['total_dry_mass_pg']),
                biomass_change_percent=100*(float(p['total_dry_mass_pg'])/rec['initial_dry_mass_pg']-1),
                minimum_glucose_mM=glucose[p['time_minutes']],mean_glucose_mM=mean_glucose[p['time_minutes']]))
        for p in rows(run/'inputs/benchmark_cells.csv'): per_update.append(dict(case_id=c['case_id'],**p))
        rec['flags']=';'.join(t['diagnostic_flags']); records.append(rec)
        dest=out/'data'/c['case_id']; dest.mkdir()
        files=[run/n for n in ('manifest.json','metrics.json','hardware.json','stdout.log','stderr.log','resource.tsv')]
        files += [run/'inputs'/n for n in ('settings.xml','benchmark_metrics.json','benchmark_cells.csv','benchmark_update_counts.csv')]
        for p in files:
            if p.exists():
                shutil.copy2(p,dest/p.name); copied[str((dest/p.name).relative_to(out))]=digest(p)
        for p in list((run/'inputs').glob('benchmark_*.csv'))+[run/'manifest.json',run/'metrics.json']:
            hashes[str(p.resolve())]=digest(p)
    table(out/'tables/outcomes.csv',records); table(out/'tables/trajectories.csv',trajectories)
    table(out/'tables/intracellular_updates.csv',per_update)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for phase,name in [('timestep','timestep_outcomes'),('refinement','cancer_refinement')]:
        models=['ecoli_core','mcf7_core'] if phase=='timestep' else ['mcf7_core']
        fig,axes=plt.subplots(3,len(models),figsize=(6*len(models),10),squeeze=False)
        for col,model in enumerate(models):
            group=sorted((r for r in records if r['phase']==phase and r['model']==model),key=lambda r:(r['ratio'],-r['diffusion_dt_minutes']))
            for r in group:
                curve=[p for p in trajectories if p['case_id']==r['case_id']]
                label=f"Ratio {r['ratio']:g}" if phase=='timestep' else f"Both dt = {r['diffusion_dt_minutes']:g} min"
                if r['flags']: label+=' (flagged)'
                for row,key in enumerate(('biomass_change_percent','mean_glucose_mM','minimum_glucose_mM')):
                    axes[row,col].plot([p['time_minutes'] for p in curve],[p[key] for p in curve],label=label,
                                      linestyle='--' if r['flags'] else '-')
            axes[0,col].set_title('E. coli' if model=='ecoli_core' else 'Cancer (MCF7 core)')
            axes[0,col].set_ylabel('Biomass change from initialization (%)')
            axes[1,col].set_ylabel('Mean glucose across domain (mM)')
            axes[2,col].set_ylabel('Minimum glucose (mM)')
            for ax in axes[:,col]: ax.set_xlabel('Simulation time (min)'); ax.legend(fontsize=8); ax.grid(alpha=.2)
        fig.tight_layout()
        for suffix in ('png','pdf'): fig.savefig(out/'plots'/f'{name}.{suffix}',dpi=180)
        plt.close(fig)
    for name in ('campaign.json','study.json'): shutil.copy2(args.campaign/name,out/name)
    write_json(out/'analysis.json',dict(script_sha256=digest(__file__),slurm_job_id=os.environ.get('SLURM_JOB_ID'),
        expected_cases=len(expected),observed_cases=len(records),within_model_inputs_verified=True,
        source_evidence_sha256=hashes,copied_evidence_sha256=copied,
        interpretation='Provisional 10-minute pilots; flags retained; no yield ground truth or accuracy tolerance assumed.'))
    print(json.dumps([{k:r[k] for k in ('case_id','biomass_change_percent','minimum_glucose_mM','actual_updates','solver_failures','flags')} for r in records],indent=2))


if __name__=='__main__': main()
