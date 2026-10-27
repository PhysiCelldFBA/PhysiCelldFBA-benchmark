#!/usr/bin/env python3
"""Extract sample media, exchange kinetics and model identities without running simulations."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from common import digest,write_json

from common import SOURCE as ROOT
def enabled(node): return node is not None and node.get('enabled','false').lower()=='true'
def number(node,default=None): return float(node.text) if node is not None and node.text and node.text.strip() else default

def model_asset(config,name):
    if not name: return None
    for p in (config.parent.parent/name,config.parent/name,config.parent/Path(name).name):
        if p.is_file(): return p.resolve()
    return None

def sbml_info(path):
    root=ET.parse(path).getroot()
    parameters={n.get('id'):float(n.get('value')) for n in root.iter() if n.tag.split('}')[-1]=='parameter' and n.get('value')}
    reactions=[]
    for n in root.iter():
        if n.tag.split('}')[-1]!='reaction': continue
        a={k.split('}')[-1]:v for k,v in n.attrib.items()}
        reactions.append(dict(id=n.get('id'),lower=parameters.get(a.get('lowerFluxBound')),upper=parameters.get(a.get('upperFluxBound'))))
    return dict(path=str(path.relative_to(ROOT)),sha256=digest(path),reactions=len(reactions),
                species=sum(n.tag.split('}')[-1]=='species' for n in root.iter()),
                required_positive_fluxes=[r for r in reactions if r['lower'] is not None and r['lower']>0],
                objectives=[{k.split('}')[-1]:v for k,v in n.attrib.items()} for n in root.iter() if n.tag.split('}')[-1]=='fluxObjective'])

def audit():
    records=[]; models={}
    for config in sorted((ROOT/'sample_projects_intracellular/fba').rglob('*.xml')):
        root=ET.parse(config).getroot()
        if root.tag!='PhysiCell_settings': continue
        fields=[]
        for n in root.findall('microenvironment_setup/variable'):
            fields.append(dict(name=n.get('name'),initial=number(n.find('initial_condition')),
                initial_units=n.find('initial_condition').get('units') if n.find('initial_condition') is not None else None,
                diffusion=number(n.find('physical_parameter_set/diffusion_coefficient')),
                boundary_all_enabled=enabled(n.find('Dirichlet_boundary_condition')),
                boundary_all_value=number(n.find('Dirichlet_boundary_condition')),
                faces=[dict(face=f.get('ID'),enabled=enabled(f),value=number(f)) for f in n.findall('Dirichlet_options/boundary_value')]))
        cells=[]
        for c in root.findall('cell_definitions/cell_definition'):
            m=c.find('phenotype/intracellular')
            if m is None: continue
            name=m.findtext('settings/sbml_filename'); asset=model_asset(config,name)
            if asset and str(asset) not in models: models[str(asset)]=sbml_info(asset)
            volume=number(c.find('phenotype/volume/total'))
            fluid=number(c.find('phenotype/volume/fluid_fraction'))
            density=number(m.find('growth_model/cell_density'))
            cells.append(dict(name=c.get('name'),parent_type=c.get('parent_type'),sbml_reference=name,
                model=models.get(str(asset)),volume_um3=volume,fluid_fraction=fluid,cell_density=density,
                dry_mass_pg=volume*(1-fluid)*density if None not in (volume,fluid,density) else None,
                growth_settings={n.tag:n.text for n in m.findall('growth_model/*')},
                death_enabled=enabled(m.find('death_model')),
                death_settings={n.tag:n.text for n in m.findall('death_model/*')},
                intracellular_dt=m.findtext('settings/intracellular_dt',m.findtext('settings/time_step')),
                exchanges=[dict(field=e.get('substrate'),reaction=e.findtext('fba_flux'),Km=number(e.find('Km')),Vmax=number(e.find('Vmax')),
                    Km_units=e.find('Km').get('units') if e.find('Km') is not None else None,
                    Vmax_units=e.find('Vmax').get('units') if e.find('Vmax') is not None else None) for e in m.findall('transport_model/exchange')]))
        records.append(dict(config=str(config.relative_to(ROOT)),sha256=digest(config),project=config.parent.parent.name,
            domain={n.tag:n.text for n in root.findall('domain/*')},
            timesteps={n.tag:n.text for n in root.findall('overall/*')},fields=fields,cells=cells,
            user_parameters={n.tag:n.text for n in root.findall('user_parameters/*')},
            external_conditions=ET.tostring(root.find('microenvironment_setup/options'),encoding='unicode') if root.find('microenvironment_setup/options') is not None else None))
    return records

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); records=audit(); args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'sample_conditions.json',records)
    flat=[]
    for r in records:
        for f in r['fields']:
            flat.append(dict(config=r['config'],field=f['name'],initial=f['initial'],units=f['initial_units'],
                             all_faces_enabled=f['boundary_all_enabled'],all_faces_value=f['boundary_all_value'],
                             explicit_active_faces=json.dumps([x for x in f['faces'] if x['enabled']],sort_keys=True)))
    with (args.output/'media.csv').open('x',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    print(f'Extracted {len(records)} configs and {len(flat)} field definitions; no simulations run.')

if __name__=='__main__': main()
