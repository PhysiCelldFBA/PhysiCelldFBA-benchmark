#!/usr/bin/env python3
"""Screen extracted source-supplied media with static one-cell LPs, not simulations."""
import argparse
import copy
import csv
from pathlib import Path
import subprocess
from common import digest,read_json,write_json

from common import SOURCE as ROOT

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); inventory=read_json(a.inventory); a.output.mkdir(parents=True,exist_ok=False)
    choices=[('ecoli_mass','dfba_unit_test/config/Unit_test_mass_conversion.xml'),
             ('ecoli_colony','bacterial_colony/config/PhysiCell_settings.xml'),
             ('ecoli_static','ecoli_acetic_switch/config/PhysiCell_settings_static_condition.xml'),
             ('cancer_native','cancer_core_metabolism/config/PhysiCell_settings.xml'),
             ('iml_native','ecoli_acetic_switch/config/Ecoli_large_scale.xml'),
             ('recon_native','cancer_metabolism/config/PhysiCell_settings.xml'),
             ('crossfeeding','crossfeeding/config/PhysiCell_settings_crossfeeding.xml')]
    profiles=[]
    for name,suffix in choices:
        r=next(r for r in inventory if r['config'].endswith('/'+suffix))
        for cell in r['cells']:
            profiles.append(dict(name=name+'-'+cell['name'],source=r,cell=cell,overrides={}))
    cancer=next(p for p in profiles if p['name'].startswith('cancer_native'))
    for oxygen in (.75,1,2):
        profile=copy.deepcopy(cancer);profile.update(name=f'cancer_candidate_o2_{oxygen}',overrides={'O2':oxygen});profiles.append(profile)
    # Explicitly record the currently planned network substitution, which uses
    # small-cell E. coli physiology rather than the native large-scale sample.
    template=next(r for r in inventory if r['config'].endswith('/ecoli_acetic_switch/config/PhysiCell_settings.xml'))
    profile=dict(name='iml_benchmark_template',source=template,cell=copy.deepcopy(template['cells'][0]),overrides={})
    profile['cell']['model']=next(p for p in profiles if p['name'].startswith('iml_native'))['cell']['model']
    profiles.append(profile)
    summary=[]; details=[]
    for profile in profiles:
        r,c=profile['source'],profile['cell']; model=c['model']
        if model is None: raise ValueError('Unresolved SBML')
        medium={f['name']:max([f['initial'] or 0]+[x['value'] or 0 for x in f['faces'] if x['enabled']]+([f['boundary_all_value'] or 0] if f['boundary_all_enabled'] else [])) for f in r['fields']}
        medium.update(profile['overrides'])
        voxel=1
        for axis in 'xyz': voxel*=float(r['domain']['d'+axis])
        mass=c['dry_mass_pg']*1e-12
        objective=model['objectives']
        if len(objective)!=1 or float(objective[0]['coefficient'])!=1: raise ValueError('Unsupported multiobjective model')
        objective=objective[0]['reaction']
        for dt in (.01,.1,1):
            name=profile['name']+'-dt'+str(dt); directory=a.output/name;directory.mkdir()
            limits=[]; changes=[]
            death=c['death_settings']
            if c['death_enabled'] and death.get('death_trigger_flux'):
                limits.append((death['death_trigger_flux'],float(death['death_flux_threshold'])))
            for ex in c['exchanges']:
                concentration=medium[ex['field']]
                kinetic=ex['Vmax']*concentration/(ex['Km']+concentration) if concentration>0 else 0
                amount=concentration*voxel/1e15; request=kinetic*dt/60*mass
                rate=kinetic*amount/request if request>amount+1e-18 else kinetic
                limits.append((ex['reaction'],-rate))
                changes.append(dict(field=ex['field'],concentration_mM=concentration,kinetic_max=kinetic,capped_max=rate))
            bounds=directory/'bounds.tsv';bounds.write_text(''.join(f'{rxn}\t{lb:.17g}\n' for rxn,lb in limits))
            cmd=[str(a.binary.resolve()),str(ROOT/model['path']),objective,c['growth_settings']['max_growth_rate'],str(bounds.resolve()),str((directory/'solution.tsv').resolve())]
            result=subprocess.run(cmd,capture_output=True,text=True)
            (directory/'stdout.log').write_text(result.stdout);(directory/'stderr.log').write_text(result.stderr)
            if result.returncode: raise ValueError(f'LP check failed: {name}: {result.returncode}')
            with (directory/'solution.tsv').open() as stream: answer=next(csv.DictReader(stream,delimiter='\t'))
            record=dict(profile=profile['name'],dt_minutes=dt,status=answer['status'],growth_per_hour=float(answer['growth_per_hour']),
                        unmapped_uptake_reactions=int(answer['unmapped_boundary_reactions_allowing_uptake']),
                        source_config=r['config'],model=model['path'],model_sha256=model['sha256'],mass_pg=c['dry_mass_pg'],voxel_um3=voxel,
                        overrides=str(profile['overrides']))
            summary.append(record); details.append(dict(**record,medium_mM=medium,bounds=changes,
                configured_objective=c['growth_settings']['objective_reaction'],sbml_objective_used=objective,
                interpretation='Uniform local concentrations at source-supply levels; static LP only; no gradients, injections, diffusion, exchange caching, population or time integration tested.'))
    with (a.output/'summary.csv').open('x',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    write_json(a.output/'details.json',details)
    write_json(a.output/'provenance.json',dict(binary_sha256=digest(a.binary),script_sha256=digest(__file__),inventory_sha256=digest(a.inventory),
        note='Same SBML objective; mapped kinetic bounds with current one-cell voxel-window cap and epsilon; unmapped SBML bounds retained. Growth cap applied as the engine does, irrespective of XML unit label.'))
    print(f'Completed {len(summary)} static LP checks; no simulations run.')

if __name__=='__main__': main()
